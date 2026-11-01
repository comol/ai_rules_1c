# meta-validate v1.45 — Validate 1C metadata object structure (Python port)
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills, pinned at
#         2e75b0f483eb020e9f09562d1a7be1982bc5ac6e — the same upstream state the
#         vendored meta-validate.ps1 was synced from.
# Licence: MIT, Copyright (c) 2025-2026 Nick Shirokov. Full notice and permission
#          text: ../../../NOTICE.md (installed as
#          skills/1c-metadata-manage/NOTICE.md).
# Local (same in meta-validate.ps1): form registrations are scalar references
#        that resolve to Forms/<Name>.xml, a descriptor that parses and declares
#        the same name (6a-6d); every GeneratedType category is required and
#        named exactly (2); a Default*/Auxiliary* object, record or list form
#        has that role by its main attribute type (6f, on top of the reference
#        check 20); a form binds Description / Code only when the length is
#        positive (6g), and the main object form shows a mandatory Description
#        nobody fills (6h, warning); names are unique case-insensitively across
#        attributes, tabular sections, dimensions, resources, addressing
#        attributes and accounting flags (8, one report per clash);
#        InformationRegister forbids Periodicity and DefaultRecordSetForm (12);
#        a type spelled with an export folder name (cfg:Catalogs.X) is an
#        error (16a). Format versions follow upstream check 24 (part vs
#        descriptor = error, object vs the dump = warning); the former local
#        checks 1e / 6e are retired.
import argparse
import os
import re
import sys

from lxml import etree

# В batch скрипт выполняется повторно в том же процессе, и поток может оказаться подменённым
# (у StringIO нет reconfigure) — кодировка к этому моменту уже выставлена первым прогоном.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# Регистронезависимый ввод — паритет с PS1: в PowerShell имена параметров и [ValidateSet]
# регистр не различают, в argparse совпадение точное.
def ci_parse_args(parser, argv=None):
    """parse_args по правилам PS: имена параметров и значения choices регистронезависимы."""
    argv = list(sys.argv[1:] if argv is None else argv)
    names = {s.lower(): s for a in parser._actions for s in a.option_strings}
    for i, tok in enumerate(argv):
        if tok.startswith('-') and tok.lower() in names:
            argv[i] = names[tok.lower()]
    # choices — зеркало [ValidateSet]; канонизируем ДО разбора, иначе argparse отвергнет регистр
    choice_map = {}
    for a in parser._actions:
        if a.choices:
            for s in a.option_strings:
                choice_map[s] = {str(c).lower(): c for c in a.choices}
    for i in range(len(argv) - 1):
        m = choice_map.get(argv[i])
        if m and argv[i + 1].lower() in m:
            argv[i + 1] = m[argv[i + 1].lower()]
    return parser.parse_args(argv)


# ── arg parsing ──────────────────────────────────────────────

parser = argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument("-ObjectPath", "-Path", required=True)
parser.add_argument("-Detailed", action="store_true")
parser.add_argument("-MaxErrors", type=int, default=30)
parser.add_argument("-OutFile", default="")
args = ci_parse_args(parser)

detailed = args.Detailed
max_errors = args.MaxErrors
out_file = args.OutFile

# ── batch mode: pipe-separated paths ─────────────────────────

path_list = [p.strip() for p in args.ObjectPath.split('|') if p.strip()]
if len(path_list) > 1:
    # Каждый объект проверяется этим же скриптом в СВЕЖЕМ globals() — так же, как PS-порт вызывает
    # себя через & (тот же процесс, новая область видимости). Отдельный процесс на объект стоил бы
    # старта интерпретатора с импортом lxml (~146 мс) при разборе в единицы миллисекунд; здесь и
    # старт, и компиляция файла платятся один раз на весь батч.
    batch_ok = 0
    batch_fail = 0
    with open(__file__, encoding="utf-8") as _f:
        _code = compile(_f.read(), __file__, "exec")
    _saved_argv = sys.argv
    for single_path in path_list:
        argv = ["meta-validate.py", "-ObjectPath", single_path, "-MaxErrors", str(max_errors)]
        if detailed:
            argv.append("-Detailed")
        if out_file:
            base, ext = os.path.splitext(out_file)
            obj_leaf = os.path.splitext(os.path.basename(single_path))[0]
            argv += ["-OutFile", f"{base}_{obj_leaf}{ext}"]
        sys.argv = argv
        rc = 0
        try:
            exec(_code, {"__name__": "__main__", "__file__": __file__})
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 0
        except Exception as e:
            # Падение одного объекта не должно рвать батч — в варианте с отдельным процессом
            # это обеспечивалось изоляцией процессов.
            print(f"[ERROR] {single_path}: {type(e).__name__}: {e}")
            rc = 1
        finally:
            sys.argv = _saved_argv
        if rc == 0:
            batch_ok += 1
        else:
            batch_fail += 1
    print()
    print(f"=== Batch: {len(path_list)} objects, {batch_ok} passed, {batch_fail} failed ===")
    sys.exit(1 if batch_fail > 0 else 0)

object_path = path_list[0]

# ── resolve path ─────────────────────────────────────────────

if not os.path.isabs(object_path):
    object_path = os.path.join(os.getcwd(), object_path)

if os.path.isdir(object_path):
    dir_name = os.path.basename(object_path)
    candidate = os.path.join(object_path, f"{dir_name}.xml")
    sibling = os.path.join(os.path.dirname(object_path), f"{dir_name}.xml")
    if os.path.exists(candidate):
        object_path = candidate
    elif os.path.exists(sibling):
        object_path = sibling
    else:
        xml_files = [f for f in os.listdir(object_path) if f.endswith(".xml")]
        if xml_files:
            object_path = os.path.join(object_path, xml_files[0])
        else:
            print(f"[ERROR] No XML file found in directory: {object_path}")
            sys.exit(1)

# File not found -- прощающий ввод для плоских объектов (SessionParameter, CommonAttribute,
# DefinedType, WSReference, ... -- один .xml без папки): дописать .xml к голому имени
if not os.path.exists(object_path) and not os.path.splitext(object_path)[1]:
    if os.path.exists(object_path + ".xml"):
        object_path = object_path + ".xml"

# File not found -- check Dir/Name/Name.xml -> Dir/Name.xml
if not os.path.exists(object_path):
    file_name = os.path.splitext(os.path.basename(object_path))[0]
    parent_dir = os.path.dirname(object_path)
    parent_dir_name = os.path.basename(parent_dir)
    if file_name == parent_dir_name:
        candidate = os.path.join(os.path.dirname(parent_dir), f"{file_name}.xml")
        if os.path.exists(candidate):
            object_path = candidate

if not os.path.exists(object_path):
    print(f"[ERROR] File not found: {object_path}")
    sys.exit(1)

resolved_path = os.path.abspath(object_path)

# ── detect config directory (for cross-object checks) ────────

config_dir = None
probe = os.path.dirname(resolved_path)
for _ in range(4):
    if not probe:
        break
    if os.path.exists(os.path.join(probe, "Configuration.xml")):
        config_dir = probe
        break
    probe = os.path.dirname(probe)

# ── output infrastructure ────────────────────────────────────

errors = 0
warnings = 0
ok_count = 0
stopped = False
output_lines = []


def out_line(msg):
    output_lines.append(msg)


def report_ok(msg):
    global ok_count
    ok_count += 1
    if detailed:
        out_line(f"[OK]    {msg}")


def report_error(msg):
    global errors, stopped
    errors += 1
    out_line(f"[ERROR] {msg}")
    if errors >= max_errors:
        stopped = True


def report_warn(msg):
    global warnings
    warnings += 1
    out_line(f"[WARN]  {msg}")


def finalize():
    checks = ok_count + errors + warnings
    if errors == 0 and warnings == 0 and not detailed:
        result = f"=== Validation OK: {md_type}.{obj_name} ({checks} checks) ==="
    else:
        out_line("")
        if stopped and errors >= max_errors:
            out_line(f"Stopped after {max_errors} errors. Fix and re-run.")
        out_line(f"=== Result: {errors} errors, {warnings} warnings ({checks} checks) ===")
        result = "\n".join(output_lines)
    print(result)
    if out_file:
        with open(out_file, "w", encoding="utf-8-sig") as f:
            f.write(result)
        print(f"Written to: {out_file}")


# ── Format version ───────────────────────────────────────────
# Проверенный диапазон версий формата выгрузки: 2.17 (8.3.24) … 2.21 (8.5). Полная лестница —
# docs/1c-configuration-spec.md, «Лестница версий». Версию задаёт платформа ВЫГРУЗКИ, а не режим
# совместимости конфигурации. Версии ниже 2.17 (платформы 8.3.23 и старше) существуют, но навыки
# на них не проверялись — это предупреждение о непокрытии, а не о некорректности файла.
FORMAT_VERIFIED_MIN = "2.17"
FORMAT_VERIFIED_MAX = "2.21"


def format_rank(ver):
    """"2.20" → 220, "2.9" → 209. Строковое сравнение неверно ("2.9" > "2.17")."""
    m = re.match(r'^(\d+)\.(\d+)$', ver or '')
    return int(m.group(1)) * 100 + int(m.group(2)) if m else 0


# Штамп версии формата — атрибут version КОРНЕВОГО элемента файла. Именно корневого: в Form.xml
# расширения ниже стоит <BaseForm version=…>. Читается только заголовок, без разбора файла.
def root_version(xml_path):
    if not os.path.isfile(xml_path):
        return None
    with open(xml_path, "rb") as f:
        head = f.read(4096).decode("utf-8", errors="ignore")
    m = re.search(r'<[A-Za-z_][\w.:-]*(\s[^>]*)?/?>', head)
    if not m:
        return None
    v = re.search(r'(?:^|\s)version="([^"]*)"', m.group(1) or "")
    if v:
        return v.group(1)
    return None


# Корень автономной внешней обработки/отчёта. Копия общего эталона (семья is_external_root,
# авторитет — cf-edit).
def _sg_is_external_root(xml_path):
    if not os.path.isfile(xml_path):
        return False
    try:
        mx = etree.parse(xml_path).getroot()
        for child in mx:
            if isinstance(child.tag, str):
                return child.tag.split("}")[-1] in ("ExternalDataProcessor", "ExternalReport")
    except Exception:
        return False
    return False


# Якорь выгрузки, в чьём дереве лежит файл: корень автономной EPF/ERF либо Configuration.xml,
# ближайший вверх. Корень обработки проверяется первым — иначе обработка, лежащая в дереве
# конфигурации, сверялась бы с конфигурацией. Нет якоря — сверять не с чем.
def find_dump_anchor(start_dir):
    d = start_dir
    for _ in range(15):
        if not d:
            break
        if _sg_is_external_root(d + ".xml"):
            return d + ".xml"
        cfg = os.path.join(d, "Configuration.xml")
        if os.path.exists(cfg):
            return cfg
        parent = os.path.dirname(d)
        if not parent or parent == d:
            break
        d = parent
    return None


# ── Reference tables ─────────────────────────────────────────

guid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
ident_pattern = re.compile(r'^[A-Za-z\u0410-\u042F\u0401\u0430-\u044F\u0451_][A-Za-z0-9\u0410-\u042F\u0401\u0430-\u044F\u0451_]*$')

valid_types = (
    "Catalog", "Document", "Enum", "Constant",
    "InformationRegister", "AccumulationRegister", "AccountingRegister", "CalculationRegister",
    "ChartOfAccounts", "ChartOfCharacteristicTypes", "ChartOfCalculationTypes",
    "BusinessProcess", "Task", "ExchangePlan", "DocumentJournal",
    "Report", "DataProcessor",
    "CommonModule", "ScheduledJob", "EventSubscription",
    "HTTPService", "WebService", "DefinedType",
    # Внешний источник данных и его таблица (корень файла таблицы — <Table>).
    "ExternalDataSource", "Table",
)

# Валидные типы метаданных без глубоких правил валидации — раньше падали как "Unrecognized"
# (ложная ошибка на валидном объекте). Для них выполняется базовая структурная проверка (root/uuid/Name).
structural_only_types = (
    "Subsystem", "Role", "CommonForm", "CommonCommand", "CommandGroup", "CommonAttribute",
    "CommonTemplate", "CommonPicture", "SessionParameter", "SettingsStorage", "FilterCriterion",
    "IntegrationService", "Bot",
    "FunctionalOption", "FunctionalOptionsParameter", "Language", "Style", "StyleItem",
    "WSReference", "XDTOPackage", "DocumentNumerator", "Sequence",
)

# Вложенные дескрипторы объекта: Forms/<Имя>.xml и Templates/<Имя>.xml. Корень тот же MetaDataObject,
# но в ChildObjects конфигурации они не регистрируются и первым сегментом MDObjectRef не бывают —
# в known_roots проверки 17 их не добавлять. Принимаются, чтобы пакетный прогон по списку изменённых
# файлов не падал на них «Unrecognized».
nested_descriptor_types = ("Form", "Template")
# Вид формы/макета — по нему платформа выбирает читателя тела. Значения — docs/1c-configuration-spec.md,
# свойства FormType и TemplateType. Список отдельный от valid_property_values: у авторитета meta-compile
# этих ключей нет (формы и макеты создают form-add и template-add).
descriptor_kind_values = {
    "FormType": ("Managed", "Ordinary"),
    "TemplateType": ("SpreadsheetDocument", "BinaryData", "HTMLDocument", "TextDocument", "ActiveDocument",
                     "DataCompositionSchema", "DataCompositionAppearanceTemplate", "GraphicalSchema", "GeographicalSchema", "AddIn"),
}

# GeneratedType categories by type
generated_type_categories = {
    "Catalog":                    ["Object", "Ref", "Selection", "List", "Manager"],
    "Document":                   ["Object", "Ref", "Selection", "List", "Manager"],
    "Enum":                       ["Ref", "Manager", "List"],
    "Constant":                   ["Manager", "ValueManager", "ValueKey"],
    "InformationRegister":        ["Record", "Manager", "Selection", "List", "RecordSet", "RecordKey", "RecordManager"],
    "AccumulationRegister":       ["Record", "Manager", "Selection", "List", "RecordSet", "RecordKey"],
    "AccountingRegister":         ["Record", "Manager", "Selection", "List", "RecordSet", "RecordKey", "ExtDimensions"],
    "CalculationRegister":        ["Record", "Manager", "Selection", "List", "RecordSet", "RecordKey", "Recalcs"],
    "ChartOfAccounts":            ["Object", "Ref", "Selection", "List", "Manager", "ExtDimensionTypes", "ExtDimensionTypesRow"],
    "ChartOfCharacteristicTypes": ["Object", "Ref", "Selection", "List", "Manager", "Characteristic"],
    "ChartOfCalculationTypes":    ["Object", "Ref", "Selection", "List", "Manager", "DisplacingCalculationTypes", "DisplacingCalculationTypesRow", "BaseCalculationTypes", "BaseCalculationTypesRow", "LeadingCalculationTypes", "LeadingCalculationTypesRow"],
    "BusinessProcess":            ["Object", "Ref", "Selection", "List", "Manager", "RoutePointRef"],
    "Task":                       ["Object", "Ref", "Selection", "List", "Manager"],
    "ExchangePlan":               ["Object", "Ref", "Selection", "List", "Manager"],
    "DocumentJournal":            ["Selection", "List", "Manager"],
    "Report":                     ["Object", "Manager"],
    "DataProcessor":              ["Object", "Manager"],
    "DefinedType":                ["DefinedType"],
    "ExternalDataSource":         ["Manager", "TablesManager", "CubesManager"],
    # Таблица внешнего источника: имя элемента трёхчастное (Префикс.Источник.Таблица),
    # но проверка «имя оканчивается на .ИмяОбъекта» на нём работает как есть.
    "Table":                      ["Manager", "Object", "Ref", "List", "Record", "RecordSet", "RecordKey", "RecordManager"],
}

# Types that have NO InternalInfo / GeneratedType
types_without_internal_info = ("CommonModule", "ScheduledJob", "EventSubscription")

# StandardAttributes by type
standard_attributes_by_type = {
    "Catalog":                    ["PredefinedDataName", "Predefined", "Ref", "DeletionMark", "IsFolder", "Owner", "Parent", "Description", "Code"],
    "Document":                   ["Posted", "Ref", "DeletionMark", "Date", "Number"],
    "Enum":                       ["Order", "Ref"],
    "InformationRegister":        ["Active", "LineNumber", "Recorder", "Period"],
    "AccumulationRegister":       ["Active", "LineNumber", "Recorder", "Period", "RecordType"],
    "AccountingRegister":         ["Active", "Period", "Recorder", "LineNumber", "Account", "PeriodAdjustment", "RecordType"],
    "CalculationRegister":        ["Active", "Recorder", "LineNumber", "RegistrationPeriod", "CalculationType", "ReversingEntry", "ActionPeriod", "BegOfActionPeriod", "EndOfActionPeriod", "BegOfBasePeriod", "EndOfBasePeriod"],
    "ChartOfAccounts":            ["PredefinedDataName", "Predefined", "Ref", "DeletionMark", "Description", "Code", "Parent", "Order", "Type", "OffBalance"],
    "ChartOfCharacteristicTypes": ["PredefinedDataName", "Predefined", "Ref", "DeletionMark", "Description", "Code", "Parent", "IsFolder", "ValueType"],
    "ChartOfCalculationTypes":    ["PredefinedDataName", "Predefined", "Ref", "DeletionMark", "Description", "Code", "ActionPeriodIsBasic"],
    "BusinessProcess":            ["Ref", "DeletionMark", "Date", "Number", "Started", "Completed", "HeadTask"],
    "Task":                       ["Ref", "DeletionMark", "Date", "Number", "Executed", "Description", "RoutePoint", "BusinessProcess"],
    "ExchangePlan":               ["Ref", "DeletionMark", "Code", "Description", "ThisNode", "SentNo", "ReceivedNo", "ExchangeDate"],
    "DocumentJournal":            ["Type", "Ref", "Date", "Posted", "DeletionMark", "Number"],
}

# Стандартные реквизиты, присутствие которых зависит от свойств объекта: у бухрегистра
# PeriodAdjustment — от длины периода корректировки, RecordType — от корреспонденции; у регистра
# накопления RecordType — от вида регистра. Их отсутствие законно, в «Missing» не попадают.
std_attr_conditional_names = {
    "AccountingRegister":   ("PeriodAdjustment", "RecordType"),
    "AccumulationRegister": ("RecordType",),
    # ExchangeDate — легаси-реквизит, объявлен лишь у части планов обмена: допустим, но не обязателен.
    "ExchangePlan":         ("ExchangeDate",),
}

# Types that have StandardAttributes block
types_with_std_attrs = (
    "Catalog", "Document", "Enum",
    "InformationRegister", "AccumulationRegister", "AccountingRegister", "CalculationRegister",
    "ChartOfAccounts", "ChartOfCharacteristicTypes", "ChartOfCalculationTypes",
    "BusinessProcess", "Task", "ExchangePlan", "DocumentJournal",
)

def reserved_command_names():
    """Имена стандартных команд вида — англ. и рус., в нижнем регистре: команда объекта с таким именем
    не загрузится («Имя команды не может совпадать с именем стандартной команды»; регистр не важен, от
    UseStandardCommands не зависит — замер 8.3.24/8.3.27). Вида нет в карте — ограничения нет
    (перечисление, план обмена; критерий отбора и таблица внешнего источника не замерены)."""
    open_list = {"openlist", "открытьсписок"}
    create = {"create", "создать"}
    folder = {"createfolder", "создатьгруппу"}
    by_value = {"openbyvalue", "открытьпозначению"}
    based_on = {"createbasedon", "создатьнаосновании"}
    return {
        "Catalog":                    open_list | create | folder | by_value | based_on,
        "ChartOfCharacteristicTypes": open_list | create | folder | based_on,
        "Task":                       open_list | create | by_value | based_on,
        "Document":                   open_list | create | based_on,
        "BusinessProcess":            open_list | create | based_on,
        "ChartOfAccounts":            open_list | create | based_on,
        "ChartOfCalculationTypes":    open_list | create | based_on,
        "InformationRegister":        open_list | create | by_value,
        "AccumulationRegister":       open_list,
        "AccountingRegister":         open_list,
        "CalculationRegister":        open_list,
        "DocumentJournal":            open_list,
        "DataProcessor":              {"open", "открыть"},
        "Report":                     {"open", "открыть"},
    }

def object_child_order():
    """Порядок групп в <ChildObjects> объекта по виду. Это xs:sequence <Вид>ChildObjects из MDClasses XSD,
    сверенный выгрузкой платформы: выгрузка сама ставит группы в этот порядок, так что вставка не на место
    даёт дифф при следующей выгрузке. Единого порядка нет — у документа Form стоит до TabularSection."""
    return {
        "Catalog":                    ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "Document":                   ["Attribute", "Form", "TabularSection", "Template", "Command"],
        "ExchangePlan":               ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "ChartOfCharacteristicTypes": ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "ChartOfAccounts":            ["Attribute", "TabularSection", "AccountingFlag", "ExtDimensionAccountingFlag", "Form", "Template", "Command"],
        "ChartOfCalculationTypes":    ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "BusinessProcess":            ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "Task":                       ["Attribute", "TabularSection", "Form", "Template", "AddressingAttribute", "Command"],
        "DataProcessor":              ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "Report":                     ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "ExternalDataProcessor":      ["Attribute", "TabularSection", "Form", "Template"],
        "ExternalReport":             ["Attribute", "TabularSection", "Form", "Template"],
        "Enum":                       ["EnumValue", "Form", "Template", "Command"],
        "InformationRegister":        ["Resource", "Attribute", "Dimension", "Form", "Template", "Command"],
        "AccumulationRegister":       ["Resource", "Attribute", "Dimension", "Form", "Template", "Command"],
        "AccountingRegister":         ["Dimension", "Resource", "Attribute", "Form", "Template", "Command"],
        "CalculationRegister":        ["Resource", "Attribute", "Dimension", "Recalculation", "Form", "Template", "Command"],
        "DocumentJournal":            ["Column", "Form", "Template", "Command"],
        "Table":                      ["Field", "Form", "Command", "Template"],
        "ExternalDataSource":         ["Table", "Cube", "Function"],
        "Cube":                       ["DimensionTable", "Dimension", "Resource", "Form", "Command", "Template"],
        "DimensionTable":             ["Field", "Form", "Command", "Template"],
        "FilterCriterion":            ["Form", "Command"],
        "SettingsStorage":            ["Form", "Template"],
        "TabularSection":             ["Attribute"],
    }


# ChildObjects rules
child_object_rules = {
    "Catalog":                    ["Attribute", "TabularSection", "Form", "Template", "Command"],
    "Document":                   ["Attribute", "TabularSection", "Form", "Template", "Command"],
    "ExchangePlan":               ["Attribute", "TabularSection", "Form", "Template", "Command"],
    "ChartOfAccounts":            ["Attribute", "TabularSection", "Form", "Template", "Command", "AccountingFlag", "ExtDimensionAccountingFlag"],
    "ChartOfCharacteristicTypes": ["Attribute", "TabularSection", "Form", "Template", "Command"],
    "ChartOfCalculationTypes":    ["Attribute", "TabularSection", "Form", "Template", "Command"],
    "BusinessProcess":            ["Attribute", "TabularSection", "Form", "Template", "Command"],
    "Task":                       ["Attribute", "TabularSection", "Form", "Template", "Command", "AddressingAttribute"],
    "Report":                     ["Attribute", "TabularSection", "Form", "Template", "Command"],
    "DataProcessor":              ["Attribute", "TabularSection", "Form", "Template", "Command"],
    "Enum":                       ["EnumValue", "Form", "Template", "Command"],
    "InformationRegister":        ["Dimension", "Resource", "Attribute", "Form", "Template", "Command"],
    "AccumulationRegister":       ["Dimension", "Resource", "Attribute", "Form", "Template", "Command"],
    "AccountingRegister":         ["Dimension", "Resource", "Attribute", "Form", "Template", "Command"],
    "CalculationRegister":        ["Dimension", "Resource", "Attribute", "Form", "Template", "Command", "Recalculation"],
    "DocumentJournal":            ["Column", "Form", "Template", "Command"],
    "HTTPService":                ["URLTemplate"],
    "WebService":                 ["Operation"],
    # Внешний источник: таблицы перечислены именами, функции лежат полными узлами.
    "ExternalDataSource":         ["Table", "Function", "Cube"],
    "Table":                      ["Field", "Form", "Template", "Command"],
    "Constant":                   ["Form"],
    "DefinedType":                [],
    "CommonModule":               [],
    "ScheduledJob":               [],
    "EventSubscription":          [],
}

# Группы командного интерфейса (зеркало meta-compile): раздела — без commandParameterType; формы — с параметром.
SECTION_COMMAND_GROUPS = ["NavigationPanelImportant", "NavigationPanelOrdinary", "NavigationPanelSeeAlso",
                          "ActionsPanelCreate", "ActionsPanelReports", "ActionsPanelTools"]
FORM_COMMAND_GROUPS = ["FormCommandBarImportant", "FormCommandBarCreateBasedOn",
                       "FormNavigationPanelImportant", "FormNavigationPanelGoTo", "FormNavigationPanelSeeAlso"]
VALID_COMMAND_GROUPS = SECTION_COMMAND_GROUPS + FORM_COMMAND_GROUPS

# Valid enum property values
valid_property_values = {
    "CodeType":                     ["String", "Number"],
    "CodeAllowedLength":            ["Variable", "Fixed"],
    "NumberType":                   ["String", "Number"],
    "NumberAllowedLength":          ["Variable", "Fixed"],
    "Posting":                      ["Allow", "Deny"],
    "RealTimePosting":              ["Allow", "Deny"],
    "RegisterRecordsDeletion":      ["AutoDelete", "AutoDeleteOnUnpost", "AutoDeleteOff"],
    "RegisterRecordsWritingOnPost": ["WriteModified", "WriteSelected"],
    # AutomaticAndManaged — только у внешнего источника данных и его таблиц.
    "DataLockControlMode":          ["Automatic", "Managed", "AutomaticAndManaged"],
    "FullTextSearch":               ["Use", "DontUse"],
    "DefaultPresentation":          ["AsDescription", "AsCode"],
    # Уточнение по виду объекта («Вид.Свойство») — раньше общего списка. AsNumber («в виде номера»)
    # есть только у задачи: у справочника и прочих платформа его отвергает (8.3.24 и 8.5.1).
    "Task.DefaultPresentation":     ["AsDescription", "AsNumber"],
    "HierarchyType":                ["HierarchyFoldersAndItems", "HierarchyOfItems"],
    "EditType":                     ["InDialog", "InList", "BothWays"],
    "WriteMode":                    ["Independent", "RecorderSubordinate"],
    "InformationRegisterPeriodicity": ["Nonperiodical", "Second", "Day", "Month", "Quarter", "Year", "RecorderPosition"],
    "RegisterType":                 ["Balance", "Turnovers"],
    "ReturnValuesReuse":            ["DontUse", "DuringRequest", "DuringSession"],
    "ReuseSessions":                ["DontUse", "Use", "AutoUse"],
    "FillChecking":                 ["DontCheck", "ShowError"],
    "Indexing":                     ["DontIndex", "Index", "IndexWithAdditionalOrder"],
    "DataHistory":                  ["Use", "DontUse"],
    "CreateOnInput":                ["Auto", "Use", "DontUse"],
    "ChoiceHistoryOnInput":         ["Auto", "DontUse"],
    "DependenceOnCalculationTypes": ["DontUse", "OnActionPeriod", "OnRegistrationPeriod"],
    # Значения — по XSD платформы; не встреченные в выгрузках БП/УНФ/ERP подтверждены загрузкой и
    # выгрузкой на 8.3.24 и 8.5.1. Имя с разным смыслом у разных владельцев — только ключом «Контекст.Свойство».
    "ChoiceFoldersAndItems": ["Items", "Folders", "FoldersAndItems"],
    "NumberPeriodicity": ["Nonperiodical", "Year", "Quarter", "Month", "Day"],
    "ParameterUseMode": ["Single", "Multiple"],
    "Representation": ["Auto", "Text", "Picture", "PictureAndText"],
    "OnMainServerUnavalableBehavior": ["Auto", "MakeDisable", "DontChangeBehavior"],
    "FormType": ["Managed", "Ordinary"],
    "MoveBoundaryOnPosting": ["DontMove", "Move"],
    "SequenceFilling": ["AutoFill", "AutoFillOff"],
    "TaskNumberAutoPrefix": ["BusinessProcessNumber", "DontUse"],
    "AutoUse": ["DontUse", "Use"],
    "DataSeparation": ["DontUse", "Separate"],
    "UsersSeparation": ["DontUse", "Separate"],
    "AuthenticationSeparation": ["DontUse", "Separate"],
    "ConfigurationExtensionsSeparation": ["DontUse", "Separate"],
    "SeparatedDataUse": ["Independently", "IndependentlyAndSimultaneously"],
    "TemplateType": ["SpreadsheetDocument", "BinaryData", "ActiveDocument", "HTMLDocument", "TextDocument", "GeographicalSchema", "GraphicalSchema", "DataCompositionSchema", "DataCompositionAppearanceTemplate", "AddIn"],
    "UseInInterfaceCompatibilityMode": ["Any", "Taxi", "Version85"],
    "TypeReductionMode": ["TransformValues", "DeleteData", "Deny"],
    "TransactionsIsolationLevel": ["Auto", "ReadUncommitted", "ReadCommitted", "RepeatableRead", "Serializable"],
    "TableType": ["Table", "Expression"],
    "TableDataType": ["NonobjectData", "ObjectData"],
    "ChoiceDataGetModeOnInputByString": ["Directly", "Background"],
    "HTTPMethod": ["GET", "HEAD", "PUT", "POST", "DELETE", "PATCH", "MERGE", "OPTIONS", "TRACE", "CONNECT", "PROPFIND", "PROPPATCH", "MOVE", "COPY", "LOCK", "UNLOCK", "MKCOL", "Any"],
    "TransferDirection": ["In", "Out", "InOut"],
    "ValueChange": ["Clear", "DontChange"],
    # QuickChoice у справочника и других ссылочных — булево; перечислением он бывает здесь:
    "Constant.QuickChoice": ["Auto", "Use", "DontUse"],
    "CommonAttribute.QuickChoice": ["Auto", "Use", "DontUse"],
    "Attribute.QuickChoice": ["Auto", "Use", "DontUse"],
    # Use: у реквизита и ТЧ — для групп/элементов; у состава общего реквизита — Auto/Use/DontUse;
    # у регламентного задания — булево, у параметра функциональных опций — список (общего ключа нет).
    "Attribute.Use": ["ForItem", "ForFolder", "ForFolderAndItem"],
    "TabularSection.Use": ["ForItem", "ForFolder", "ForFolderAndItem"],
    "CommonAttributeContent.Use": ["Auto", "Use", "DontUse"],
}

# Properties forbidden per type (would cause LoadConfigFromFiles error)
forbidden_properties = {
    "ChartOfCharacteristicTypes": ["CodeType"],
    "ChartOfAccounts":            ["Autonumbering", "Hierarchical"],
    "ChartOfCalculationTypes":    ["CheckUnique", "Autonumbering"],
    "ExchangePlan":               ["CodeType", "CheckUnique", "Autonumbering"],
    # Local: the periodicity property is InformationRegisterPeriodicity, and an
    # information register has no record-set default form.
    "InformationRegister":        ["Periodicity", "DefaultRecordSetForm"],
}

# GeneratedType names that do not follow <Type><Category>.<Name> (Designer dumps).
generated_type_prefix_exceptions = {
    ("DefinedType", "DefinedType"): "DefinedType",
    ("ChartOfCharacteristicTypes", "Characteristic"): "Characteristic",
    ("CalculationRegister", "Recalcs"): "RecalculationsManager",
    ("ChartOfCalculationTypes", "DisplacingCalculationTypes"): "DisplacingCalculationTypes",
    ("ChartOfCalculationTypes", "DisplacingCalculationTypesRow"): "DisplacingCalculationTypesRow",
    ("ChartOfCalculationTypes", "BaseCalculationTypes"): "BaseCalculationTypes",
    ("ChartOfCalculationTypes", "BaseCalculationTypesRow"): "BaseCalculationTypesRow",
    ("ChartOfCalculationTypes", "LeadingCalculationTypes"): "LeadingCalculationTypes",
    ("ChartOfCalculationTypes", "LeadingCalculationTypesRow"): "LeadingCalculationTypesRow",
}

# Export folder names that are sometimes written where a type belongs
# (cfg:Catalogs.X instead of cfg:CatalogRef.X) -> the reference type, if any.
export_folder_types = {
    "Catalogs": "CatalogRef", "Documents": "DocumentRef", "Enums": "EnumRef",
    "ChartsOfAccounts": "ChartOfAccountsRef",
    "ChartsOfCharacteristicTypes": "ChartOfCharacteristicTypesRef",
    "ChartsOfCalculationTypes": "ChartOfCalculationTypesRef",
    "BusinessProcesses": "BusinessProcessRef", "ExchangePlans": "ExchangePlanRef",
    "Tasks": "TaskRef", "DefinedTypes": "DefinedType",
    "InformationRegisters": "", "AccumulationRegisters": "", "AccountingRegisters": "",
    "CalculationRegisters": "", "Constants": "", "DataProcessors": "", "Reports": "",
    "DocumentJournals": "",
}

# An assignment of the standard Description in BSL (6h): "<x>.Наименование =" or a
# bare "Наименование =" at the start of a line in an object module.
DESCRIPTION_ASSIGNMENT = re.compile(r"(?im)(?:\.\s*|^[ \t]*)(?:Наименование|Description)\s*=(?!=)")

# Default*Form / Auxiliary*Form property -> role its form must have. Choice forms are
# not role-checked: vendor configurations point DefaultChoiceForm at object forms.
default_form_roles = {
    "DefaultObjectForm": "object", "AuxiliaryObjectForm": "object",
    "DefaultFolderForm": "object", "AuxiliaryFolderForm": "object",
    "DefaultRecordForm": "record", "AuxiliaryRecordForm": "record",
    "DefaultListForm": "list", "AuxiliaryListForm": "list",
}

# ── Namespaces ───────────────────────────────────────────────

NS = {
    "md":  "http://v8.1c.ru/8.3/MDClasses",
    "v8":  "http://v8.1c.ru/8.1/data/core",
    "xr":  "http://v8.1c.ru/8.3/xcf/readable",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "xs":  "http://www.w3.org/2001/XMLSchema",
    "cfg": "http://v8.1c.ru/8.1/data/enterprise/current-config",
}

MD_NS = NS["md"]


def local_name(node):
    return etree.QName(node.tag).localname


def find(parent, xpath):
    r = parent.xpath(xpath, namespaces=NS)
    return r[0] if r else None


def find_all(parent, xpath):
    return parent.xpath(xpath, namespaces=NS)


def inner_text(node):
    if node is None:
        return ""
    return node.text or ""


def text_of(node):
    if node is None:
        return ""
    return (node.text or "").strip()


# ── 1. Parse XML ─────────────────────────────────────────────

out_line("")

tree = None
try:
    parser_xml = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(resolved_path, parser_xml)
except Exception as e:
    out_line("=== Validation: (parse failed) ===")
    out_line("")
    report_error(f"1. XML parse failed: {e}")
    finalize()
    sys.exit(1)

root = tree.getroot()

# ── Check 1: Root structure ──────────────────────────────────

check1_ok = True

if local_name(root) != "MetaDataObject":
    report_error(f"1. Root element is '{local_name(root)}', expected 'MetaDataObject'")
    finalize()
    sys.exit(1)

expected_ns = "http://v8.1c.ru/8.3/MDClasses"
root_ns = etree.QName(root.tag).namespace or ""
if root_ns != expected_ns:
    report_error(f"1. Root namespace is '{root_ns}', expected '{expected_ns}'")
    check1_ok = False

# Version attribute
version = root.get("version", "")
version_rank = format_rank(version)
if not version:
    report_warn("1. Missing version attribute on MetaDataObject")
elif version_rank == 0:
    report_error(f"1. Malformed version '{version}' (expected N.N)")
elif version_rank < format_rank(FORMAT_VERIFIED_MIN):
    report_warn(f"1. Format version '{version}' is below the tested range "
                f"{FORMAT_VERIFIED_MIN}-{FORMAT_VERIFIED_MAX} — skills were not verified on it")
elif version_rank > format_rank(FORMAT_VERIFIED_MAX):
    report_warn(f"1. Format version '{version}' is above the tested range "
                f"{FORMAT_VERIFIED_MIN}-{FORMAT_VERIFIED_MAX} — skills were not verified on it")

# Detect type element -- exactly one child element in md namespace
type_node = None
md_type = ""
child_elements = []
for child in root:
    if isinstance(child.tag, str) and etree.QName(child.tag).namespace == expected_ns:
        child_elements.append(child)

if len(child_elements) == 0:
    report_error("1. No metadata type element found inside MetaDataObject")
    finalize()
    sys.exit(1)
elif len(child_elements) > 1:
    names = [local_name(c) for c in child_elements]
    report_error(f"1. Multiple type elements found: {names}")
    check1_ok = False

type_node = child_elements[0]
md_type = local_name(type_node)

if md_type not in valid_types and md_type not in structural_only_types and md_type not in nested_descriptor_types:
    report_error(f"1. Unrecognized metadata type: {md_type}")
    finalize()
    sys.exit(1)

# UUID on type element
type_uuid = type_node.get("uuid", "")
if not type_uuid:
    report_error(f"1. Missing uuid on <{md_type}> element")
    check1_ok = False
elif not guid_pattern.match(type_uuid):
    report_error(f"1. Invalid uuid '{type_uuid}' on <{md_type}>")
    check1_ok = False

# Get object name early for header
props_node = find(type_node, "md:Properties")
name_node = find(props_node, "md:Name") if props_node is not None else None
obj_name = inner_text(name_node) if name_node is not None and inner_text(name_node) else "(unknown)"

# Now emit header — insert at beginning
output_lines.insert(0, f"=== Validation: {md_type}.{obj_name} ===")

if check1_ok:
    report_ok(f"1. Root structure: MetaDataObject/{md_type}, version {version}")

# ── Check 24: версия формата согласована внутри объекта; сверка с выгрузкой ──
# Части объекта — дескриптор X.xml и штампованные тела X/Ext/*.xml — платформа загружает только в одной
# версии: «Версия формата загружаемого файла … отличается от версии формата ранее загруженных файлов».
# Формы и макеты объекта (Forms/F.xml + F/Ext/Form.xml, Templates/T.xml + T/Ext/Template.xml) — такие же
# пары, проверяются вместе с объектом. Объекты разных версий между собой платформа грузит, это лишь неоднородность выгрузки (типично после
# мержа веток, выгруженных разными платформами) — поэтому сверка с выгрузкой только предупреждает.
# Стоит до ранних выходов: нужна каждому корню, включая structural-only и вложенные дескрипторы.
obj_base_dir = os.path.dirname(resolved_path)
obj_dir = os.path.join(obj_base_dir, os.path.splitext(os.path.basename(resolved_path))[0])
ver_descriptors = [resolved_path]
for sub in ("Forms", "Templates"):
    sub_dir = os.path.join(obj_dir, sub)
    if not os.path.isdir(sub_dir):
        continue
    names = sorted(n for n in os.listdir(sub_dir)
                   if n.lower().endswith(".xml") and os.path.isfile(os.path.join(sub_dir, n)))
    for n in names:
        ver_descriptors.append(os.path.join(sub_dir, n))


def ver_rel(p):
    return p[len(obj_base_dir):].lstrip("\\/").replace("\\", "/")


ver_errors = 0
ver_bodies = 0
for desc in ver_descriptors:
    if stopped:
        break
    desc_ver = version if desc == resolved_path else root_version(desc)
    if not desc_ver:
        continue
    ext_dir = os.path.join(os.path.dirname(desc), os.path.splitext(os.path.basename(desc))[0], "Ext")
    if not os.path.isdir(ext_dir):
        continue
    body_names = sorted(n for n in os.listdir(ext_dir)
                        if n.lower().endswith(".xml") and os.path.isfile(os.path.join(ext_dir, n)))
    for bn in body_names:
        body = os.path.join(ext_dir, bn)
        body_ver = root_version(body)
        if not body_ver:
            continue
        # У заимствованной формы расширения второй штамп — <BaseForm version=…>; платформа сверяет с
        # дескриптором и его.
        if bn == "Form.xml":
            with open(body, "r", encoding="utf-8-sig") as f:
                body_text = f.read()
            bfm = re.search(r'<BaseForm\s[^>]*?version="([^"]*)"', body_text)
            if bfm and bfm.group(1) != desc_ver:
                ver_errors += 1
                report_error(f"24. {ver_rel(body)} <BaseForm> is stamped {bfm.group(1)}, its descriptor {ver_rel(desc)} "
                             f"{desc_ver} — the platform refuses to load parts of one object in different formats")
                if stopped:
                    break
        if body_ver == desc_ver:
            ver_bodies += 1
            continue
        ver_errors += 1
        report_error(f"24. {ver_rel(body)} is stamped {body_ver}, its descriptor {ver_rel(desc)} {desc_ver} "
                     "— the platform refuses to load parts of one object in different formats")
        if stopped:
            break
if ver_errors == 0 and ver_bodies > 0:
    report_ok(f"24. Format version: {ver_bodies} stamped part(s) agree with their descriptors")
dump_anchor = find_dump_anchor(obj_base_dir)
dump_ver = root_version(dump_anchor) if dump_anchor else None
if dump_ver:
    ver_off = []
    for desc in ver_descriptors:
        dv = version if desc == resolved_path else root_version(desc)
        if dv and dv != dump_ver:
            ver_off.append(f"{ver_rel(desc)} {dv}")
    if ver_off:
        shown = ", ".join(ver_off[:5])
        if len(ver_off) > 5:
            shown += f", … (+{len(ver_off) - 5})"
        report_warn(f"24. Format version differs from the dump ({dump_ver}): {shown} — the platform loads it, "
                    "but the dump is no longer uniform (typical after merging branches dumped by different platforms)")
    else:
        report_ok(f"24. Format version: matches the dump ({dump_ver})")

# Проверка 4 — значения свойств-перечислений. Блоком: её зовут и для видов без глубоких правил
# (общая форма, команда, общий реквизит, макет…) — иначе их перечисления не проверялись вовсе.
def check4():
    if props_node is not None:
        enum_checked = 0
        check4_ok = True

        # Общие свойства плюс свойства, заданные только для своего вида («Constant.QuickChoice»):
        # остальные ключи с точкой — уточнения чужих видов и контекстов (реквизит, состав), не корня
        root_props = [k for k in valid_property_values if "." not in k]
        root_props += [k[len(md_type) + 1:] for k in valid_property_values if k.startswith(f"{md_type}.")]
        for prop_name in dict.fromkeys(root_props):
            allowed = valid_property_values.get(prop_name)
            prop_node = find(props_node, f"md:{prop_name}")
            if prop_node is not None and inner_text(prop_node):
                val = inner_text(prop_node)
                allowed = valid_property_values.get(f"{md_type}.{prop_name}") or allowed
                if val not in allowed:
                    report_error(f"4. Property '{prop_name}' has invalid value '{val}' (allowed: {', '.join(allowed)})")
                    check4_ok = False
                enum_checked += 1

        # Значения у реквизитов, измерений, ресурсов и табличных частей: QuickChoice здесь — перечисление
        # (в корне справочника — булево), Use у реквизита и ТЧ — для групп/элементов. Ключи «Attribute.*»,
        # «TabularSection.*»; иначе — общий ключ свойства.
        child_common4 = ["CreateOnInput", "FullTextSearch", "DataHistory", "ChoiceHistoryOnInput"]
        co_node4 = find(type_node, "md:ChildObjects")
        items4 = []
        if co_node4 is not None:
            for ch in co_node4:
                if not isinstance(ch.tag, str):
                    continue
                items4.append(ch)
                if local_name(ch) == "TabularSection":
                    items4.extend(find_all(ch, "md:ChildObjects/md:Attribute"))
        for it in items4:
            it_props = find(it, "md:Properties")
            if it_props is None:
                continue
            ctx = "TabularSection" if local_name(it) == "TabularSection" else "Attribute"
            if ctx == "TabularSection":
                names = ["Use"]
            elif local_name(it) == "Attribute":
                names = ["QuickChoice", "ChoiceFoldersAndItems", "Use"] + child_common4
            else:
                names = ["QuickChoice", "ChoiceFoldersAndItems"] + child_common4
            it_name = find(it_props, "md:Name")
            for pn in names:
                pnode = find(it_props, f"md:{pn}")
                if pnode is None or not inner_text(pnode):
                    continue
                allowed = valid_property_values.get(f"{ctx}.{pn}") or valid_property_values.get(pn)
                if not allowed:
                    continue
                if inner_text(pnode) not in allowed:
                    report_error(f"4. {local_name(it)} '{inner_text(it_name) if it_name is not None else ''}': property '{pn}' has invalid value '{inner_text(pnode)}' (allowed: {', '.join(allowed)})")
                    check4_ok = False
                enum_checked += 1
        # Состав общего реквизита: Use элемента состава — Auto/Use/DontUse
        for cu in find_all(props_node, "md:Content/xr:Item/xr:Use"):
            allowed = valid_property_values.get("CommonAttributeContent.Use")
            if inner_text(cu) and inner_text(cu) not in allowed:
                report_error(f"4. Content item: property 'Use' has invalid value '{inner_text(cu)}' (allowed: {', '.join(allowed)})")
                check4_ok = False
            enum_checked += 1

        # Корневой <Type> (дескриптор типа значения — Константа, ПВХ) должен быть структурным:
        # <v8:Type>/<v8:TypeSet>, а не скалярный текст. Скаляр = повреждённый тип (напр. после
        # старого meta-edit modify-property Type). См. issue #42. У элемента стиля <Type> — вид элемента
        # (Color/Font/Border), скаляр там штатный.
        root_type_el = find(props_node, "md:Type") if md_type != "StyleItem" else None
        if root_type_el is not None:
            scalar_text = inner_text(root_type_el).strip()
            v8_types = find_all(root_type_el, "v8:Type")
            v8_type_sets = find_all(root_type_el, "v8:TypeSet")
            if len(v8_types) == 0 and len(v8_type_sets) == 0 and scalar_text:
                report_error(f"4. Property <Type> contains scalar text '{scalar_text}' without a type structure (<v8:Type>/<v8:TypeSet>) — corrupted value type descriptor")
                check4_ok = False

        if check4_ok:
            report_ok(f"4. Property values: {enum_checked} enum properties checked")
    else:
        report_warn("4. No Properties block to check")


# ── Structural-only types: базовая проверка (Name) и значения перечислений, без type-specific правил ──
if md_type in structural_only_types:
    if obj_name == "(unknown)":
        report_error("3. Properties: missing or empty Name")
    elif not ident_pattern.match(obj_name):
        report_error(f"3. Properties: Name '{obj_name}' is not a valid 1C identifier")
    else:
        report_ok(f'3. Properties: Name="{obj_name}" (basic structure check for {md_type})')
    check4()
    finalize()
    sys.exit(1 if errors > 0 else 0)

# ── Вложенные дескрипторы Form/Template: Name и вид формы/макета ──
if md_type in nested_descriptor_types:
    if obj_name == "(unknown)":
        report_error("3. Properties: missing or empty Name")
    elif not ident_pattern.match(obj_name):
        report_error(f"3. Properties: Name '{obj_name}' is not a valid 1C identifier")
    else:
        report_ok(f'3. Properties: Name="{obj_name}" (basic structure check for {md_type})')
    kind_prop = "FormType" if md_type == "Form" else "TemplateType"
    kind_node = find(props_node, f"md:{kind_prop}") if props_node is not None else None
    kind_value = inner_text(kind_node) if kind_node is not None else ""
    allowed = descriptor_kind_values[kind_prop]
    if not kind_value:
        report_error(f"3. Property '{kind_prop}' is missing on <{md_type}>")
    elif kind_value not in allowed:
        report_error(f"3. Property '{kind_prop}' has invalid value '{kind_value}' (allowed: {', '.join(allowed)})")
    else:
        report_ok(f"3. Property '{kind_prop}' = {kind_value}")
    finalize()
    sys.exit(1 if errors > 0 else 0)

if stopped:
    finalize()
    sys.exit(1)

# ── Check 2: InternalInfo ────────────────────────────────────

internal_info = find(type_node, "md:InternalInfo")

if md_type in types_without_internal_info:
    if internal_info is not None:
        gen_types = find_all(internal_info, "xr:GeneratedType")
        if len(gen_types) > 0:
            report_warn(f"2. InternalInfo: {md_type} should not have GeneratedType entries, found {len(gen_types)}")
        else:
            report_ok(f"2. InternalInfo: absent or empty (correct for {md_type})")
    else:
        report_ok(f"2. InternalInfo: absent (correct for {md_type})")
elif md_type in generated_type_categories:
    expected_categories = generated_type_categories[md_type]
    if internal_info is None:
        report_error(f"2. InternalInfo: missing (expected {len(expected_categories)} GeneratedType)")
    else:
        gen_types = find_all(internal_info, "xr:GeneratedType")
        check2_ok = True
        found_categories = []

        for gt in gen_types:
            gt_name = gt.get("name", "")
            gt_category = gt.get("category", "")
            found_categories.append(gt_category)

            # Validate name format: exactly <Type><Category>.<Name> for a known category
            if gt_name and obj_name != "(unknown)":
                if gt_category in expected_categories:
                    prefix = generated_type_prefix_exceptions.get((md_type, gt_category), md_type + gt_category)
                    expected_name = f"{prefix}.{obj_name}"
                    if md_type == "Table":
                        # ExternalDataSources/<Source>/Tables/<Table>.xml -> ExternalDataSourceTable<Category>.<Source>.<Table>
                        tables_dir = os.path.dirname(resolved_path)
                        eds_name = (os.path.basename(os.path.dirname(tables_dir))
                                    if os.path.basename(tables_dir) == "Tables" else "")
                        expected_name = (f"ExternalDataSourceTable{gt_category}.{eds_name}.{obj_name}"
                                         if eds_name else gt_name)
                    if gt_name != expected_name:
                        report_error(f"2. GeneratedType '{gt_category}' name '{gt_name}' — expected '{expected_name}'")
                        check2_ok = False
                elif not gt_name.endswith(f".{obj_name}"):
                    report_error(f"2. GeneratedType name '{gt_name}' does not end with '.{obj_name}'")
                    check2_ok = False

            # Validate category
            if gt_category not in expected_categories:
                report_warn(f"2. Unexpected GeneratedType category '{gt_category}' for {md_type}")

            # Validate TypeId and ValueId UUIDs
            type_id = find(gt, "xr:TypeId")
            value_id = find(gt, "xr:ValueId")
            if type_id is not None and not guid_pattern.match(inner_text(type_id)):
                report_error(f"2. Invalid TypeId UUID in GeneratedType '{gt_category}'")
                check2_ok = False
            if value_id is not None and not guid_pattern.match(inner_text(value_id)):
                report_error(f"2. Invalid ValueId UUID in GeneratedType '{gt_category}'")
                check2_ok = False

        # ExchangePlan: check for ThisNode
        if md_type == "ExchangePlan":
            this_node = find(internal_info, "xr:ThisNode")
            if this_node is None:
                report_warn("2. ExchangePlan missing xr:ThisNode in InternalInfo")
            elif not guid_pattern.match(inner_text(this_node)):
                report_error("2. ExchangePlan xr:ThisNode has invalid UUID")
                check2_ok = False

        # Check count mismatch
        missing_cats = [c for c in expected_categories if c not in found_categories]
        if missing_cats and md_type == "Table":
            report_warn(f"2. Missing GeneratedType categories: {', '.join(missing_cats)}")
        elif missing_cats:
            report_error(f"2. Missing GeneratedType categories: {', '.join(missing_cats)} — "
                         f"every category of {md_type} is required")
            check2_ok = False

        if check2_ok:
            cat_list = ", ".join(sorted(found_categories))
            report_ok(f"2. InternalInfo: {len(gen_types)} GeneratedType ({cat_list})")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 3: Properties -- Name, Synonym ─────────────────────

if props_node is None:
    report_error("3. Properties block missing")
else:
    check3_ok = True

    # Name
    if name_node is None or not inner_text(name_node):
        report_error("3. Properties: Name is missing or empty")
        check3_ok = False
    else:
        name_val = inner_text(name_node)
        if not ident_pattern.match(name_val):
            report_error(f"3. Properties: Name '{name_val}' is not a valid 1C identifier")
            check3_ok = False
        if len(name_val) > 80:
            report_warn(f"3. Properties: Name '{name_val}' is longer than 80 characters ({len(name_val)})")

    # Synonym
    syn_node = find(props_node, "md:Synonym")
    syn_present = False
    if syn_node is not None:
        syn_item = find(syn_node, "v8:item")
        if syn_item is not None:
            syn_content = find(syn_item, "v8:content")
            if syn_content is not None and inner_text(syn_content):
                syn_present = True

    if check3_ok:
        syn_info = "Synonym present" if syn_present else "no Synonym"
        report_ok(f'3. Properties: Name="{obj_name}", {syn_info}')

if stopped:
    finalize()
    sys.exit(1)

# ── Check 4: Property values -- enum properties ──────────────

check4()

if stopped:
    finalize()
    sys.exit(1)

# ── Check 5: StandardAttributes ──────────────────────────────

if md_type in types_with_std_attrs:
    std_attr_node = find(props_node, "md:StandardAttributes")
    if std_attr_node is None:
        report_ok(f"5. StandardAttributes: absent (optional for {md_type})")
    else:
        std_attrs = find_all(std_attr_node, "xr:StandardAttribute")
        expected_std_attrs = standard_attributes_by_type.get(md_type, [])
        check5_ok = True

        found_names = []
        for sa in std_attrs:
            sa_name = sa.get("name", "")
            if sa_name:
                found_names.append(sa_name)
                if sa_name not in expected_std_attrs:
                    # AccountingRegister: пары субконто, число которых задаётся планом счетов
                    is_dynamic = (md_type == "AccountingRegister" and
                                  (re.match(r'^ExtDimension\d+$', sa_name) or
                                   re.match(r'^ExtDimensionType\d+$', sa_name)))
                    if not is_dynamic:
                        report_warn(f"5. Unexpected StandardAttribute '{sa_name}' for {md_type}")
            else:
                report_error("5. StandardAttribute without 'name' attribute")
                check5_ok = False

        if expected_std_attrs:
            cond_names = std_attr_conditional_names.get(md_type, ())
            missing_attrs = [a for a in expected_std_attrs if a not in found_names and a not in cond_names]
            if missing_attrs:
                report_warn(f"5. Missing StandardAttributes: {', '.join(missing_attrs)}")

        if check5_ok:
            report_ok(f"5. StandardAttributes: {len(std_attrs)} entries")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 6: ChildObjects -- allowed element types ───────────

child_obj_node = find(type_node, "md:ChildObjects")
allowed_children = child_object_rules.get(md_type, [])

if child_obj_node is not None:
    check6_ok = True
    child_counts = {}

    for child in child_obj_node:
        if not isinstance(child.tag, str):
            continue
        child_tag = local_name(child)

        if child_tag not in allowed_children:
            report_error(f"6. ChildObjects: disallowed element '{child_tag}' for {md_type}")
            check6_ok = False

        child_counts[child_tag] = child_counts.get(child_tag, 0) + 1

    # Порядок групп: загрузка примет любой, но выгрузка переставит по канону вида — дифф без правок
    order = object_child_order().get(md_type)
    if order:
        prev_tag, prev_rank = None, -1
        for child in child_obj_node:
            if not isinstance(child.tag, str) or local_name(child) not in order:
                continue
            group_tag = local_name(child)
            rank = order.index(group_tag)
            if rank < prev_rank:
                present = [t for t in order if t in child_counts]
                report_warn(f"6. ChildObjects order: <{group_tag}> after <{prev_tag}>; platform dump reorders "
                            f"{md_type} children as {' -> '.join(present)}")
                break
            prev_tag, prev_rank = group_tag, rank

    if check6_ok:
        summary = ", ".join(f"{k}({v})" for k, v in sorted(child_counts.items()))
        if summary:
            report_ok(f"6. ChildObjects types: {summary}")
        else:
            report_ok(f"6. ChildObjects: empty (valid for {md_type})")
elif len(allowed_children) == 0:
    report_ok(f"6. ChildObjects: absent (correct for {md_type})")
else:
    report_ok("6. ChildObjects: absent")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 6a/6b (local): form registrations are references, and they resolve ──
#
# A form is registered in ChildObjects as a scalar reference — <Form>Name</Form> —
# and described by its own file, <ObjectDir>/Forms/<Name>.xml. Both halves are
# needed and neither was checked: an inline <Form uuid=...><Properties>… block
# (what a generic child builder produces) and a reference with no file behind it
# both passed as valid, and the defect only surfaced when the Configurator tried
# to load the dump.

if child_obj_node is not None:
    form_nodes = [c for c in child_obj_node
                  if isinstance(c.tag, str) and local_name(c) == "Form"]
    if form_nodes:
        object_dir = os.path.join(
            os.path.dirname(resolved_path),
            os.path.splitext(os.path.basename(resolved_path))[0])
        forms_dir = os.path.join(object_dir, "Forms")
        check6a_ok = True
        check6b_ok = True
        check6c_ok = True
        check6d_ok = True
        resolved_forms = 0
        for form_node in form_nodes:
            inline_children = [c for c in form_node if isinstance(c.tag, str)]
            if inline_children:
                name_node = find(form_node, "md:Properties/md:Name")
                shown = (name_node.text or "").strip() if name_node is not None else ""
                shown = shown or "<без имени>"
                report_error(
                    f"6a. ChildObjects/Form '{shown}' описана вложенным дескриптором внутри "
                    f"объекта. Регистрация формы — скалярная ссылка <Form>{shown}</Form>, а "
                    f"свойства формы живут в Forms/{shown}.xml. Такую выгрузку Конфигуратор "
                    f"не загрузит; создавайте форму навыком form-add.")
                check6a_ok = False
                continue
            form_name = (form_node.text or "").strip()
            if not form_name:
                report_error("6a. ChildObjects/Form: пустая регистрация формы (нет имени)")
                check6a_ok = False
                continue
            form_meta = os.path.join(forms_dir, form_name + ".xml")
            if not os.path.isfile(form_meta):
                report_error(
                    f"6b. Форма '{form_name}' зарегистрирована в ChildObjects, но её описание "
                    f"не найдено: {form_meta}")
                check6b_ok = False
                continue
            # 6c/6d: the descriptor has to be a real, matching descriptor, not just a
            # path that exists. A scaffolder that interpolates an unescaped user
            # string writes a file the Configurator cannot read, and an existence
            # check reports that dump as valid.
            try:
                form_doc = etree.parse(form_meta)
            except etree.XMLSyntaxError as exc:
                report_error(
                    f"6c. Дескриптор формы '{form_name}' не разбирается как XML: {form_meta} "
                    f"— {exc}. Такую выгрузку Конфигуратор не загрузит.")
                check6c_ok = False
                continue
            declared_node = find(form_doc.getroot(), "md:Form/md:Properties/md:Name")
            declared = (declared_node.text or "").strip() if declared_node is not None else ""
            if not declared:
                report_error(
                    f"6d. В дескрипторе {form_meta} нет Form/Properties/Name — форма "
                    f"'{form_name}' зарегистрирована, но не описана.")
                check6d_ok = False
                continue
            if declared != form_name:
                report_error(
                    f"6d. Имя в дескрипторе не совпадает с регистрацией: {form_meta} "
                    f"описывает '{declared}', а ChildObjects ссылается на '{form_name}'.")
                check6d_ok = False
                continue
            resolved_forms += 1
        if check6a_ok:
            report_ok(f"6a. Form registrations: {len(form_nodes)} scalar reference(s)")
        if check6b_ok:
            report_ok(f"6b. Form descriptors: {resolved_forms} of {len(form_nodes)} "
                      f"resolved on disk")
        if check6c_ok:
            report_ok(f"6c. Form descriptors parse as XML: {resolved_forms}")
        if check6d_ok:
            report_ok(f"6d. Form descriptor names match their registration: {resolved_forms}")

if stopped:
    finalize()
    sys.exit(1)

# ── Checks 6f-6h (local): default-form roles, standard fields ──
#
# Form versions are check 24; whether a Default*/Auxiliary*Form reference
# resolves at all is check 20. The local checks add what neither covers:
# 6f: an object, record or list slot of this object points at a form with that
#     role (main attribute type).
# 6g: a form whose main attribute is this object binds <Main>.Description /
#     <Main>.Code only when DescriptionLength / CodeLength is positive — with 0
#     the standard attribute does not exist.

declared_forms = []
if child_obj_node is not None:
    declared_forms = [text_of(c) for c in child_obj_node
                      if isinstance(c.tag, str) and local_name(c) == "Form"
                      and len([x for x in c if isinstance(x.tag, str)]) == 0 and text_of(c)]
object_dir_path = os.path.join(os.path.dirname(resolved_path),
                               os.path.splitext(os.path.basename(resolved_path))[0])
LF_NS = "http://v8.1c.ru/8.3/xcf/logform"
form_roots = {}


def form_xml_root(form_name):
    """Parsed Ext/Form.xml of a declared managed form, or None (ordinary / absent)."""
    if form_name not in form_roots:
        path = os.path.join(object_dir_path, "Forms", form_name, "Ext", "Form.xml")
        root_el = None
        if os.path.isfile(path):
            try:
                root_el = etree.parse(path).getroot()
            except etree.XMLSyntaxError:
                root_el = None
        form_roots[form_name] = root_el
    return form_roots[form_name]


def form_main_attribute(form_root):
    """(name, [types]) of the main attribute of a managed form, or (None, [])."""
    for attr in form_root.findall(f"{{{LF_NS}}}Attributes/{{{LF_NS}}}Attribute"):
        main = attr.find(f"{{{LF_NS}}}MainAttribute")
        if main is not None and (main.text or "").strip() == "true":
            types = [(t.text or "").strip() for t in attr.iter("{http://v8.1c.ru/8.1/data/core}Type")
                     if (t.text or "").strip()]
            return attr.get("name", ""), types
    return None, []


def form_role(form_root):
    _, types = form_main_attribute(form_root)
    if types == ["cfg:DynamicList"]:
        return "list"
    if len(types) == 1 and re.match(r"^cfg:\w+Object\.", types[0]):
        return "object"
    if len(types) == 1 and re.match(r"^cfg:\w+RecordManager\.", types[0]):
        return "record"
    return ""


if props_node is not None and obj_name != "(unknown)":
    check6f_ok = True
    checked_roles = 0
    own_prefix = f"{md_type}.{obj_name}.Form."
    for prop in props_node:
        if not isinstance(prop.tag, str):
            continue
        prop_name = local_name(prop)
        if prop_name not in default_form_roles:
            continue
        ref = text_of(prop)
        # Only a declared form of this object: a missing, foreign or common form is check 20.
        if not ref.startswith(own_prefix):
            continue
        form_name = ref[len(own_prefix):]
        if "." in form_name or form_name not in declared_forms:
            continue
        form_root = form_xml_root(form_name)
        if form_root is None:
            continue
        checked_roles += 1
        expected_role = default_form_roles[prop_name]
        actual_role = form_role(form_root)
        if actual_role and actual_role != expected_role:
            report_error(f"6f. {prop_name} = '{ref}': the form is a {actual_role} form "
                         f"(main attribute type), expected a {expected_role} form")
            check6f_ok = False
    if check6f_ok and checked_roles > 0:
        report_ok(f"6f. Default form roles: {checked_roles} checked")

if props_node is not None and declared_forms and obj_name != "(unknown)":
    zero_fields = []
    for length_prop, field in (("DescriptionLength", "Description"), ("CodeLength", "Code")):
        length_node = find(props_node, f"md:{length_prop}")
        if length_node is not None and text_of(length_node) == "0":
            zero_fields.append((length_prop, field))
    if zero_fields:
        check6g_ok = True
        own_type = f"cfg:{md_type}Object.{obj_name}"
        for form_name in declared_forms:
            form_root = form_xml_root(form_name)
            if form_root is None:
                continue
            main_name, main_types = form_main_attribute(form_root)
            if not main_name or main_types != [own_type]:
                continue
            paths = {(dp.text or "").strip() for dp in form_root.iter(f"{{{LF_NS}}}DataPath")}
            for length_prop, field in zero_fields:
                if f"{main_name}.{field}" in paths:
                    report_error(f"6g. Form '{form_name}' binds '{main_name}.{field}', but {length_prop}=0 — "
                                 f"the object has no {field}")
                    check6g_ok = False
        if check6g_ok:
            report_ok(f"6g. Standard fields: no binding to a zero-length {'/'.join(f for _, f in zero_fields)}")

# 6h (warning): the main object form of an object with a mandatory Description
# (DescriptionLength > 0, FillChecking ShowError — the platform default without a
# StandardAttributes block) does not show <Main>.Description, and neither the form
# module nor the object / manager module assigns it: the item cannot be written
# from that form. A warning, not an error — the value may be filled elsewhere.
if props_node is not None and obj_name != "(unknown)":
    desc_length = text_of(find(props_node, "md:DescriptionLength"))
    default_object_ref = text_of(find(props_node, "md:DefaultObjectForm"))
    own_prefix = f"{md_type}.{obj_name}.Form."
    if (re.match(r"^\d+$", desc_length) and int(desc_length) > 0
            and default_object_ref.startswith(own_prefix)
            and default_object_ref[len(own_prefix):] in declared_forms):
        std_block = find(props_node, "md:StandardAttributes")
        fill_node = find(props_node, "md:StandardAttributes/xr:StandardAttribute[@name='Description']/xr:FillChecking")
        fill_checking = text_of(fill_node) if fill_node is not None else ("" if std_block is not None else "ShowError")
        default_form = default_object_ref[len(own_prefix):]
        form_root = form_xml_root(default_form)
        if fill_checking == "ShowError" and form_root is not None:
            main_name, main_types = form_main_attribute(form_root)
            paths = {(dp.text or "").strip() for dp in form_root.iter(f"{{{LF_NS}}}DataPath")}
            if main_name and main_types == [f"cfg:{md_type}Object.{obj_name}"] \
                    and f"{main_name}.Description" not in paths:
                assigned = False
                for rel in (os.path.join("Forms", default_form, "Ext", "Form", "Module.bsl"),
                            os.path.join("Ext", "ObjectModule.bsl"), os.path.join("Ext", "ManagerModule.bsl")):
                    module_path = os.path.join(object_dir_path, rel)
                    if os.path.isfile(module_path):
                        with open(module_path, "r", encoding="utf-8-sig") as f:
                            if DESCRIPTION_ASSIGNMENT.search(f.read()):
                                assigned = True
                                break
                if not assigned:
                    report_warn(f"6h. Default object form '{default_form}' does not show '{main_name}.Description', "
                                f"which is mandatory (DescriptionLength={desc_length}, FillChecking=ShowError), and no "
                                f"form, object or manager module assigns it — writing from this form fails unless the value "
                                f"is filled elsewhere")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 7: Child elements -- UUID, Name, Type ──────────────


def check_child_element(node, kind, require_type):
    uuid = node.get("uuid", "")
    if not uuid:
        report_error(f"7. {kind} missing uuid")
        return False
    if not guid_pattern.match(uuid):
        report_error(f"7. {kind} has invalid uuid '{uuid}'")
        return False

    el_props = find(node, "md:Properties")
    if el_props is None:
        report_error(f"7. {kind} (uuid={uuid}) missing Properties")
        return False

    el_name = find(el_props, "md:Name")
    if el_name is None or not inner_text(el_name):
        report_error(f"7. {kind} (uuid={uuid}) missing or empty Name")
        return False

    name_val = inner_text(el_name)
    if not ident_pattern.match(name_val):
        report_error(f"7. {kind} '{name_val}' has invalid identifier")
        return False

    if require_type:
        type_el = find(el_props, "md:Type")
        # Пустой <Type/> — это тип «Произвольный», штатная конструкция: в типовых так описаны
        # служебные реквизиты обработок, платформа принимает и сохраняет её без изменений
        # (проверено round-trip). Ошибкой здесь был бы отказ там, где платформа не отказывает.
        if type_el is None:
            # Блока Type нет вовсе: загрузка проходит, но платформа молча подставляет тип нового
            # реквизита — Строка(10). Загрузку это не рвёт, а замысел теряет, отсюда WARN.
            report_warn(f"7. {kind} '{name_val}' — no Type block; on load the platform substitutes String(10)")

    return True


if child_obj_node is not None:
    check7_ok = True
    check7_count = 0
    element_kinds = ("Attribute", "Dimension", "Resource", "EnumValue", "Column")

    for kind in element_kinds:
        elements = find_all(child_obj_node, f"md:{kind}")
        require_type = kind not in ("EnumValue", "Column")
        for el in elements:
            if stopped:
                break
            ok = check_child_element(el, kind, require_type)
            if not ok:
                check7_ok = False
            check7_count += 1

    if check7_ok and check7_count > 0:
        report_ok(f"7. Child elements: {check7_count} items checked (UUID, Name, Type)")
    elif check7_count == 0:
        report_ok("7. Child elements: none to check")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 7b: Reserved attribute names (типозависимо: стандартные ДАННОГО типа, EN+RU) ───────
# Совпадение имени собственного реквизита со стандартным (англ. или рус.) платформа не примет → ошибка.

RESERVED_EN_RU = {
    'Ref': 'Ссылка', 'DeletionMark': 'ПометкаУдаления', 'Code': 'Код', 'Description': 'Наименование',
    'Date': 'Дата', 'Number': 'Номер', 'Posted': 'Проведен', 'Parent': 'Родитель', 'Owner': 'Владелец',
    'IsFolder': 'ЭтоГруппа', 'Predefined': 'Предопределенный', 'PredefinedDataName': 'ИмяПредопределенныхДанных',
    'Recorder': 'Регистратор', 'Period': 'Период', 'LineNumber': 'НомерСтроки', 'Active': 'Активность',
    'Order': 'Порядок', 'Type': 'Тип', 'OffBalance': 'Забалансовый', 'RecordType': 'ВидДвижения',
    'Started': 'Стартован', 'Completed': 'Завершен', 'HeadTask': 'ВедущаяЗадача',
    'Executed': 'Выполнена', 'RoutePoint': 'ТочкаМаршрута', 'BusinessProcess': 'БизнесПроцесс',
    'ThisNode': 'ЭтотУзел', 'SentNo': 'НомерОтправленного', 'ReceivedNo': 'НомерПринятого',
    'CalculationType': 'ВидРасчета', 'RegistrationPeriod': 'ПериодРегистрации', 'ReversingEntry': 'СторноЗапись',
    'Account': 'Счет', 'ValueType': 'ТипЗначения', 'ActionPeriodIsBasic': 'ПериодДействияБазовый',
}

std_for_type = standard_attributes_by_type.get(md_type)

# Колонка ТЧ — стандартные реквизиты строки: «ТабличнаяЧасть.X - Недопустимое имя реквизита -
# НомерСтроки» (замер 8.3.24). НомерСтроки — у любого объекта, Ссылка — только у ссылочного (у обработки
# колонка Ссылка законна — замер и ERP); Номер — можно.
check7b_col_ok = True
if child_obj_node is not None:
    ts_row_reserved = {"linenumber", "номерстроки"}
    if std_for_type and "Ref" in std_for_type:
        ts_row_reserved |= {"ref", "ссылка"}
    for ts_node in find_all(child_obj_node, "md:TabularSection"):
        ts_name_node = find(ts_node, "md:Properties/md:Name")
        ts_label = inner_text(ts_name_node) if ts_name_node is not None else "?"
        for col_node in find_all(ts_node, "md:ChildObjects/md:Attribute"):
            col_name = find(col_node, "md:Properties/md:Name")
            if col_name is not None and inner_text(col_name).lower() in ts_row_reserved:
                report_error(f"7b. TabularSection.{ts_label}: column '{inner_text(col_name)}' conflicts with a standard attribute of a tabular section row")
                check7b_col_ok = False

if child_obj_node is not None and std_for_type:
    reserved_set = set()
    for en in std_for_type:
        reserved_set.add(en.lower())
        ru = RESERVED_EN_RU.get(en)
        if ru:
            reserved_set.add(ru.lower())
    check7b_ok = True
    # Измерение и ресурс регистра — те же зарезервированные имена, что у реквизита («Недопустимое имя
    # измерения - Период», замер 8.3.24)
    for attr_node in find_all(child_obj_node, 'md:Attribute | md:Dimension | md:Resource'):
        attr_props = find(attr_node, 'md:Properties')
        if attr_props is not None:
            attr_name_node = find(attr_props, 'md:Name')
            if attr_name_node is not None and inner_text(attr_name_node):
                an = inner_text(attr_name_node)
                if an.lower() in reserved_set:
                    report_error(f"7b. {local_name(attr_node)} '{an}' conflicts with a standard attribute of {md_type}")
                    check7b_ok = False
    if check7b_ok and check7b_col_ok:
        report_ok("7b. Reserved attribute names: no conflicts")
elif child_obj_node is not None and check7b_col_ok:
    report_ok(f"7b. Reserved attribute names: no conflicts (no standard set for {md_type})")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 8: Name uniqueness ─────────────────────────────────


def check_uniqueness(nodes, kind, names=None):
    """1C names are case-insensitive. Pass one shared `names` dict to check several
    kinds against each other (attributes, tabular sections, dimensions, resources,
    addressing attributes and accounting flags share one namespace)."""
    if names is None:
        names = {}
    has_dupes = False
    for node in nodes:
        el_props = find(node, "md:Properties")
        if el_props is None:
            continue
        el_name = find(el_props, "md:Name")
        if el_name is None or not inner_text(el_name):
            continue
        name_val = inner_text(el_name)
        key = name_val.lower()
        if key in names:
            other_kind, other_name = names[key]
            if other_kind == kind and other_name == name_val:
                report_error(f"8. Duplicate {kind} name: '{name_val}'")
            else:
                report_error(f"8. {kind} '{name_val}' clashes with {other_kind} '{other_name}' — "
                             f"names are case-insensitive and shared by attributes, tabular sections, "
                             f"dimensions, resources, addressing attributes and accounting flags")
            has_dupes = True
        else:
            names[key] = (kind, name_val)
    return not has_dupes


if child_obj_node is not None:
    check8_ok = True

    # Реквизит, ТЧ, измерение, ресурс, реквизит адресации и признак учёта объекта — одно пространство имён
    # без учёта регистра: платформа отвергает загрузку («Задано одинаковое имя для реквизита и табличной
    # части / измерения / ресурса / реквизита адресации», замер 8.3.24). Колонке ТЧ имя реквизита объекта
    # не мешает, признаку учёта субконто — тоже (он колонка ТЧ видов субконто). Local: one shared table,
    # so a clash is reported once, with both kinds named.
    field_names = {}
    for field_kind in ("Attribute", "TabularSection", "Dimension", "Resource", "AddressingAttribute", "AccountingFlag"):
        field_nodes = find_all(child_obj_node, f"md:{field_kind}")
        if len(field_nodes) > 0:
            if not check_uniqueness(field_nodes, field_kind, field_names):
                check8_ok = False

    # EnumValues
    evs = find_all(child_obj_node, "md:EnumValue")
    if len(evs) > 0:
        if not check_uniqueness(evs, "EnumValue"):
            check8_ok = False

    # Columns (DocumentJournal)
    cols = find_all(child_obj_node, "md:Column")
    if len(cols) > 0:
        if not check_uniqueness(cols, "Column"):
            check8_ok = False

    # URLTemplates (HTTPService)
    url_ts = find_all(child_obj_node, "md:URLTemplate")
    if len(url_ts) > 0:
        if not check_uniqueness(url_ts, "URLTemplate"):
            check8_ok = False

    # Operations (WebService)
    ops = find_all(child_obj_node, "md:Operation")
    if len(ops) > 0:
        if not check_uniqueness(ops, "Operation"):
            check8_ok = False

    if check8_ok:
        report_ok("8. Name uniqueness: all names unique")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 9: TabularSections -- internal structure ───────────

if child_obj_node is not None:
    ts_sections = find_all(child_obj_node, "md:TabularSection")
    if len(ts_sections) > 0:
        check9_ok = True
        ts_count = 0

        for ts in ts_sections:
            if stopped:
                break
            ts_count += 1

            # UUID
            ts_uuid = ts.get("uuid", "")
            if not ts_uuid or not guid_pattern.match(ts_uuid):
                report_error(f"9. TabularSection #{ts_count}: invalid or missing uuid")
                check9_ok = False

            # Name
            ts_props = find(ts, "md:Properties")
            ts_name_node = find(ts_props, "md:Name") if ts_props is not None else None
            ts_name = inner_text(ts_name_node) if ts_name_node is not None else "(unnamed)"

            if ts_name_node is None or not inner_text(ts_name_node):
                report_error(f"9. TabularSection #{ts_count}: missing or empty Name")
                check9_ok = False

            # InternalInfo with 2 GeneratedType
            ts_int_info = find(ts, "md:InternalInfo")
            if ts_int_info is not None:
                ts_gens = find_all(ts_int_info, "xr:GeneratedType")
                if len(ts_gens) < 2:
                    report_warn(f"9. TabularSection '{ts_name}': expected 2 GeneratedType, found {len(ts_gens)}")

            # Attributes inside TS
            ts_child_obj = find(ts, "md:ChildObjects")
            if ts_child_obj is not None:
                ts_attrs = find_all(ts_child_obj, "md:Attribute")
                ts_attr_names = {}
                for ta in ts_attrs:
                    ta_ok = check_child_element(ta, f"TabularSection '{ts_name}'.Attribute", True)
                    if not ta_ok:
                        check9_ok = False

                    # Check name uniqueness within TS
                    ta_props = find(ta, "md:Properties")
                    ta_name = find(ta_props, "md:Name") if ta_props is not None else None
                    if ta_name is not None and inner_text(ta_name):
                        if inner_text(ta_name) in ts_attr_names:
                            report_error(f"9. Duplicate attribute '{inner_text(ta_name)}' in TabularSection '{ts_name}'")
                            check9_ok = False
                        else:
                            ts_attr_names[inner_text(ta_name)] = True

                # StandardAttributes of TS: expect LineNumber
                if ts_props is not None:
                    ts_std_attr = find(ts_props, "md:StandardAttributes")
                    if ts_std_attr is not None:
                        ts_std_attrs = find_all(ts_std_attr, "xr:StandardAttribute")
                        has_line_number = False
                        for tsa in ts_std_attrs:
                            if tsa.get("name") == "LineNumber":
                                has_line_number = True
                        if not has_line_number:
                            report_warn(f"9. TabularSection '{ts_name}': missing LineNumber StandardAttribute")

        if check9_ok:
            report_ok(f"9. TabularSections: {ts_count} sections, structure valid")
    else:
        report_ok("9. TabularSections: none present")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 10: Cross-property consistency ─────────────────────

check10_ok = True
check10_issues = 0

if props_node is not None:
    # HierarchyType set but Hierarchical = false
    hierarchical = find(props_node, "md:Hierarchical")
    hierarchy_type = find(props_node, "md:HierarchyType")
    # HierarchyType платформа пишет всегда, независимо от Hierarchical, и при выключенной иерархии
    # просто его игнорирует (проверено: значение переживает round-trip). Дефолтное значение поэтому
    # ни о чём не говорит — предупреждаем только о явно заданном другом типе иерархии: это похоже
    # на "тип иерархии выбрали, а саму иерархию включить забыли".
    if (hierarchical is not None and hierarchy_type is not None and
            inner_text(hierarchical) == "false" and inner_text(hierarchy_type)
            and inner_text(hierarchy_type) != "HierarchyFoldersAndItems"):
        report_warn(f"10. HierarchyType='{inner_text(hierarchy_type)}' but Hierarchical=false")
        check10_issues += 1

    # Код/номер нулевой длины во вводе по строке: платформа отвергает загрузку — «Указано неверное
    # поле для ввода по строке: Код/Номер» (8.3.24, 8.5.1). Бывает после правки длины в 0 без чистки
    # InputByString (meta-edit так больше не делает, но ручную правку это не страхует).
    ibs_fields = [inner_text(f).strip() for f in find_all(props_node, "md:InputByString/xr:Field")]
    for len_prop, std_attr in (("CodeLength", "Code"), ("NumberLength", "Number")):
        len_node = find(props_node, f"md:{len_prop}")
        if len_node is None or inner_text(len_node).strip() != "0":
            continue
        hit = next((f for f in ibs_fields if f.endswith(f".StandardAttribute.{std_attr}")), None)
        if hit:
            report_error(f"10. InputByString contains '{hit}' but {len_prop}=0 — the platform rejects it (invalid input-by-string field)")
            check10_ok = False
            check10_issues += 1

    # CommonModule: no context enabled
    if md_type == "CommonModule":
        contexts = ("Server", "ClientManagedApplication", "ClientOrdinaryApplication",
                     "ExternalConnection", "ServerCall", "Global")
        any_enabled = False
        for ctx in contexts:
            ctx_node = find(props_node, f"md:{ctx}")
            if ctx_node is not None and inner_text(ctx_node) == "true":
                any_enabled = True
                break
        if not any_enabled:
            report_warn("10. CommonModule: no execution context enabled")
            check10_issues += 1

    # EventSubscription: empty Handler
    if md_type == "EventSubscription":
        handler = find(props_node, "md:Handler")
        if handler is None or not text_of(handler):
            report_error("10. EventSubscription: empty Handler")
            check10_ok = False
            check10_issues += 1

        # Empty Source
        source = find(props_node, "md:Source")
        # Источник задают и наборами типов (<v8:TypeSet>cfg:CatalogObject</v8:TypeSet>) — в типовых
        # так описана каждая четвёртая подписка. Реально пустой источник платформа отвергает:
        # «ПодпискаНаСобытие.X - Источник событий должен быть задан», поэтому это ошибка.
        has_source = False
        if source is not None:
            source_types = find_all(source, "v8:Type")
            source_type_sets = find_all(source, "v8:TypeSet")
            if len(source_types) > 0 or len(source_type_sets) > 0:
                has_source = True
        if not has_source:
            report_error("10. EventSubscription: event source is not set — the platform rejects the load")
            check10_issues += 1

    # ScheduledJob: empty MethodName
    if md_type == "ScheduledJob":
        method = find(props_node, "md:MethodName")
        if method is None or not text_of(method):
            report_error("10. ScheduledJob: empty MethodName")
            check10_ok = False
            check10_issues += 1

    # AccountingRegister: ChartOfAccounts must not be empty
    if md_type == 'AccountingRegister':
        coa = find(props_node, 'md:ChartOfAccounts')
        if coa is None or not text_of(coa):
            report_error('10. AccountingRegister: empty ChartOfAccounts')
            check10_ok = False
            check10_issues += 1
            print('[HINT] /meta-edit -Operation modify-property -Value "ChartOfAccounts=ChartOfAccounts.XXX"')

    # CalculationRegister: ChartOfCalculationTypes must not be empty
    if md_type == 'CalculationRegister':
        coct = find(props_node, 'md:ChartOfCalculationTypes')
        if coct is None or not text_of(coct):
            report_error('10. CalculationRegister: empty ChartOfCalculationTypes')
            check10_ok = False
            check10_issues += 1
            print('[HINT] /meta-edit -Operation modify-property -Value "ChartOfCalculationTypes=ChartOfCalculationTypes.XXX"')

    # BusinessProcess: Task should not be empty
    if md_type == 'BusinessProcess':
        task_prop = find(props_node, 'md:Task')
        if task_prop is None or not text_of(task_prop):
            report_warn('10. BusinessProcess: empty Task reference')
            check10_issues += 1
            print('[HINT] /meta-edit -Operation modify-property -Value "Task=Task.XXX"')

    # CalculationRegister: ActionPeriod=true requires non-empty Schedule
    if md_type == 'CalculationRegister':
        action_period = find(props_node, 'md:ActionPeriod')
        if action_period is not None and text_of(action_period) == 'true':
            schedule = find(props_node, 'md:Schedule')
            if schedule is None or not text_of(schedule):
                report_warn('10. CalculationRegister: ActionPeriod=true but Schedule is empty — platform requires a schedule register')
                check10_issues += 1

    # DocumentJournal: RegisteredDocuments should not be empty
    if md_type == 'DocumentJournal':
        reg_docs = find(props_node, 'md:RegisteredDocuments')
        # Регистрируемые документы платформа перечисляет как <xr:Item xsi:type="xr:MDObjectRef">,
        # так же их пишет meta-compile; форма с <v8:Type> сохранена на случай иных выгрузок.
        # Пустой состав платформа отвергает: «Для журнала не заданы регистрируемые документы».
        has_reg_docs = False
        if reg_docs is not None:
            items = find_all(reg_docs, 'v8:Type')
            ref_items = find_all(reg_docs, 'xr:Item')
            if len(items) > 0 or len(ref_items) > 0:
                has_reg_docs = True
        if not has_reg_docs:
            report_error('10. DocumentJournal: no registered documents — the platform rejects the load')
            check10_issues += 1

    # ChartOfAccounts: ExtDimensionTypes should be set if MaxExtDimensionCount > 0
    if md_type == 'ChartOfAccounts':
        max_ext_dim = find(props_node, 'md:MaxExtDimensionCount')
        if max_ext_dim is not None:
            try:
                med_val = int(inner_text(max_ext_dim) or '0')
            except ValueError:
                med_val = 0
            if med_val > 0:
                edt = find(props_node, 'md:ExtDimensionTypes')
                if edt is None or not text_of(edt):
                    report_warn('10. ChartOfAccounts: MaxExtDimensionCount>0 but ExtDimensionTypes is empty')
                    check10_issues += 1
                    print('[HINT] /meta-edit -Operation modify-property -Value "ExtDimensionTypes=ChartOfCharacteristicTypes.XXX"')

    # Register: must have at least one Dimension or Resource (platform rejects empty registers)
    reg_types_all = ('AccumulationRegister', 'AccountingRegister', 'CalculationRegister', 'InformationRegister')
    if md_type in reg_types_all and child_obj_node is not None:
        dims = len(find_all(child_obj_node, 'md:Dimension'))
        ress = len(find_all(child_obj_node, 'md:Resource'))
        attrs = len(find_all(child_obj_node, 'md:Attribute'))
        if dims + ress + attrs == 0:
            report_warn(f"10. {md_type}: no Dimensions, Resources, or Attributes \u2014 platform will reject")
            check10_issues += 1

    # Document: RegisterRecords references should point to existing objects in config
    if md_type == 'Document' and config_dir:
        reg_records = find(props_node, 'md:RegisterRecords')
        if reg_records is not None:
            rr_items = find_all(reg_records, 'xr:Item')
            for item in rr_items:
                ref_val = (inner_text(item) or '').strip()
                if not ref_val:
                    continue
                # Parse "AccumulationRegister.Name" -> dir AccumulationRegisters/Name
                parts = ref_val.split('.', 1)
                if len(parts) == 2:
                    ref_type, ref_name = parts
                    dir_map = {
                        'AccumulationRegister': 'AccumulationRegisters',
                        'InformationRegister': 'InformationRegisters',
                        'AccountingRegister': 'AccountingRegisters',
                        'CalculationRegister': 'CalculationRegisters',
                    }
                    ref_dir = dir_map.get(ref_type)
                    if ref_dir:
                        ref_path = os.path.join(config_dir, ref_dir, ref_name)
                        ref_xml = os.path.join(config_dir, ref_dir, ref_name + '.xml')
                        if not os.path.exists(ref_path) and not os.path.exists(ref_xml):
                            report_warn(f"10. Document.RegisterRecords references '{ref_val}' but object not found in config")
                            check10_issues += 1

    # Register: must have at least one registrar document
    register_types = ('AccumulationRegister', 'AccountingRegister', 'CalculationRegister', 'InformationRegister')
    if md_type in register_types and config_dir and obj_name != '(unknown)':
        needs_registrar = True
        # InformationRegister with WriteMode=Independent does not need a registrar
        if md_type == 'InformationRegister':
            write_mode = find(props_node, 'md:WriteMode')
            if write_mode is None or inner_text(write_mode) != 'RecorderSubordinate':
                needs_registrar = False
        if needs_registrar:
            reg_ref = f'{md_type}.{obj_name}'
            docs_dir = os.path.join(config_dir, 'Documents')
            has_registrar = False
            if os.path.isdir(docs_dir):
                for fname in os.listdir(docs_dir):
                    if not fname.endswith('.xml'):
                        continue
                    fpath = os.path.join(docs_dir, fname)
                    if not os.path.isfile(fpath):
                        continue
                    with open(fpath, 'r', encoding='utf-8-sig') as f:
                        content = f.read()
                    if reg_ref in content:
                        has_registrar = True
                        break
            if not has_registrar:
                report_warn(f"10. {md_type}: no registrar document found (none references '{reg_ref}' in RegisterRecords)")
                check10_issues += 1

if check10_ok and check10_issues == 0:
    report_ok("10. Cross-property consistency")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 11: HTTPService/WebService nested structure ────────

if md_type == "HTTPService" and child_obj_node is not None:
    url_templates = find_all(child_obj_node, "md:URLTemplate")
    check11_ok = True
    method_count = 0

    valid_http_methods = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "MERGE", "CONNECT")

    for ut in url_templates:
        if stopped:
            break

        ut_props = find(ut, "md:Properties")
        ut_name_node = find(ut_props, "md:Name") if ut_props is not None else None
        ut_name = inner_text(ut_name_node) if ut_name_node is not None else "(unnamed)"

        # Template property
        tpl = find(ut_props, "md:Template") if ut_props is not None else None
        if tpl is None or not text_of(tpl):
            report_error(f"11. HTTPService URLTemplate '{ut_name}': empty Template")
            check11_ok = False

        # Methods inside URLTemplate
        ut_child_obj = find(ut, "md:ChildObjects")
        if ut_child_obj is not None:
            methods = find_all(ut_child_obj, "md:Method")
            for m in methods:
                method_count += 1
                m_props = find(m, "md:Properties")
                if m_props is not None:
                    http_method = find(m_props, "md:HTTPMethod")
                    if http_method is not None and inner_text(http_method):
                        if inner_text(http_method) not in valid_http_methods:
                            report_error(f"11. HTTPService URLTemplate '{ut_name}': invalid HTTPMethod '{inner_text(http_method)}'")
                            check11_ok = False
                    else:
                        report_error(f"11. HTTPService URLTemplate '{ut_name}': Method missing HTTPMethod")
                        check11_ok = False

    if check11_ok:
        report_ok(f"11. HTTPService: {len(url_templates)} URLTemplate(s), {method_count} method(s)")

elif md_type == "WebService" and child_obj_node is not None:
    operations = find_all(child_obj_node, "md:Operation")
    check11_ok = True
    param_count = 0

    valid_directions = ("In", "Out", "InOut")

    for op in operations:
        if stopped:
            break

        op_props = find(op, "md:Properties")
        op_name_node = find(op_props, "md:Name") if op_props is not None else None
        op_name = inner_text(op_name_node) if op_name_node is not None else "(unnamed)"

        # ReturnType
        ret_type = find(op_props, "md:XDTOReturningValueType") if op_props is not None else None
        if ret_type is None or not text_of(ret_type):
            report_warn(f"11. WebService Operation '{op_name}': no XDTOReturningValueType")

        # Parameters inside Operation
        op_child_obj = find(op, "md:ChildObjects")
        if op_child_obj is not None:
            params = find_all(op_child_obj, "md:Parameter")
            for p in params:
                param_count += 1
                p_props = find(p, "md:Properties")
                if p_props is not None:
                    direction = find(p_props, "md:TransferDirection")
                    if direction is not None and inner_text(direction) and inner_text(direction) not in valid_directions:
                        report_error(f"11. WebService Operation '{op_name}': Parameter has invalid TransferDirection '{inner_text(direction)}'")
                        check11_ok = False

    if check11_ok:
        report_ok(f"11. WebService: {len(operations)} operation(s), {param_count} parameter(s)")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 12: Forbidden properties per type ──────────────────

if props_node is not None and md_type in forbidden_properties:
    forbidden = forbidden_properties[md_type]
    check12_ok = True
    for fp in forbidden:
        fp_node = find(props_node, f"md:{fp}")
        if fp_node is not None:
            report_error(f"12. Forbidden property '{fp}' present in {md_type} (will fail on LoadConfigFromFiles)")
            check12_ok = False
    if check12_ok:
        report_ok("12. Forbidden properties: none found")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 13: Method reference validation ─────────────────────

if props_node is not None and md_type in ("EventSubscription", "ScheduledJob") and config_dir:
    check13_ok = True
    method_ref = None
    prop_label = None

    if md_type == "EventSubscription":
        h_node = find(props_node, "md:Handler")
        if h_node is not None:
            method_ref = text_of(h_node)
        prop_label = "Handler"
    elif md_type == "ScheduledJob":
        m_node = find(props_node, "md:MethodName")
        if m_node is not None:
            method_ref = text_of(m_node)
        prop_label = "MethodName"

    if method_ref:
        parts = method_ref.split(".")
        # Format: CommonModule.ModuleName.ProcedureName (3 parts) or ModuleName.ProcedureName (2 parts, legacy)
        if len(parts) == 3 and parts[0] == "CommonModule":
            cm_name = parts[1]
            proc_name = parts[2]
        elif len(parts) == 2:
            cm_name = parts[0]
            proc_name = parts[1]
        else:
            report_error(f"13. {md_type}.{prop_label} = '{method_ref}': expected format 'CommonModule.ModuleName.ProcedureName'")
            check13_ok = False
            cm_name = None
            proc_name = None
        if cm_name:
            cm_xml = os.path.join(config_dir, "CommonModules", f"{cm_name}.xml")
            if not os.path.exists(cm_xml):
                report_error(f"13. {md_type}.{prop_label}: CommonModule '{cm_name}' not found (expected {cm_xml})")
                check13_ok = False
            else:
                # Check BSL file for exported procedure
                bsl_path = os.path.join(config_dir, "CommonModules", cm_name, "Ext", "Module.bsl")
                if os.path.exists(bsl_path):
                    with open(bsl_path, "r", encoding="utf-8-sig") as f:
                        bsl_content = f.read()
                    # Список параметров переносится на следующие строки, и Экспорт оказывается не на
                    # строке с именем — в типовых так объявлена каждая обработчик-процедура с длинной
                    # сигнатурой. Отсюда (?s) для содержимого скобок и \s (а не пробел) перед Экспорт.
                    export_pattern = rf"(?smi)^[ 	]*(Procedure|Function|Процедура|Функция)[ 	]+{re.escape(proc_name)}[ 	]*\([^)]*\)\s+(Export|Экспорт)"
                    if not re.search(export_pattern, bsl_content):
                        report_warn(f"13. {md_type}.{prop_label}: procedure '{proc_name}' not found as exported in CommonModule '{cm_name}'")
                        check13_ok = False
                elif os.path.exists(os.path.splitext(bsl_path)[0] + ".bin"):
                    # Модуль поставщика выгружен в двоичном виде (Module.bin) — текста нет by design,
                    # проверять нечего. Предупреждать здесь значило бы шуметь о норме.
                    pass
                else:
                    report_warn(f"13. {md_type}.{prop_label}: BSL file not found ({bsl_path}), cannot verify procedure")

    if check13_ok:
        report_ok(f"13. Method reference: {prop_label} = '{method_ref}'")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 14: DocumentJournal Column content ──────────────────

if md_type == "DocumentJournal" and child_obj_node is not None:
    columns = find_all(child_obj_node, "md:Column")
    check14_ok = True
    col_count = 0
    empty_ref_count = 0

    for col in columns:
        col_count += 1
        col_props = find(col, "md:Properties")
        col_name_node = find(col_props, "md:Name") if col_props is not None else None
        col_name = inner_text(col_name_node) if col_name_node is not None else "(unnamed)"

        refs = find(col_props, "md:References") if col_props is not None else None
        has_items = False
        if refs is not None:
            items = find_all(refs, "xr:Item")
            if len(items) > 0:
                has_items = True
        if not has_items:
            report_error(f"14. DocumentJournal Column '{col_name}': empty References (will fail on LoadConfigFromFiles)")
            check14_ok = False
            empty_ref_count += 1

    if check14_ok and col_count > 0:
        report_ok(f"14. DocumentJournal Columns: {col_count} column(s), all have References")
    elif col_count == 0:
        report_ok("14. DocumentJournal Columns: none")

if stopped:
    finalize()
    sys.exit(1)

# ── Check 15: Commands — Group обязателен/валиден; секц.группа несовместима с CommandParameterType ──

if child_obj_node is not None:
    commands = find_all(child_obj_node, "md:Command")
    check15_ok = True
    cmd_count = 0
    reserved_cmd = reserved_command_names().get(md_type, set())
    for cmd in commands:
        if stopped:
            break
        cmd_count += 1
        cuuid = cmd.get("uuid", "")
        cmd_props = find(cmd, "md:Properties")
        cmd_name_node = find(cmd_props, "md:Name") if cmd_props is not None else None
        cmd_name = inner_text(cmd_name_node) if (cmd_name_node is not None and inner_text(cmd_name_node)) else "(unnamed)"
        if not cuuid or not guid_pattern.match(cuuid):
            report_error(f"15. Command '{cmd_name}': missing or invalid uuid")
            check15_ok = False
        if cmd_name == "(unnamed)":
            report_error(f"15. Command (uuid={cuuid}): missing or empty Name")
            check15_ok = False
        elif cmd_name.lower() in reserved_cmd:
            report_error(f"15. Command '{cmd_name}': name conflicts with a standard command of {md_type}")
            check15_ok = False
        group_node = find(cmd_props, "md:Group") if cmd_props is not None else None
        group_val = inner_text(group_node).strip() if group_node is not None else ""
        if not group_val:
            report_error(f"15. Command '{cmd_name}': group (Group) is not set — the platform rejects the load")
            check15_ok = False
        elif group_val not in VALID_COMMAND_GROUPS and not group_val.startswith("CommandGroup."):
            report_error(f"15. Command '{cmd_name}': unknown group '{group_val}'. "
                         f"Valid: {', '.join(VALID_COMMAND_GROUPS)}; or CommandGroup.<Name>")
            check15_ok = False
        elif group_val in SECTION_COMMAND_GROUPS:
            cpt_node = find(cmd_props, "md:CommandParameterType") if cmd_props is not None else None
            has_cpt = cpt_node is not None and (len(find_all(cpt_node, "v8:Type")) > 0 or len(find_all(cpt_node, "v8:TypeSet")) > 0)
            if has_cpt:
                report_error(f"15. Command '{cmd_name}': parameter type (CommandParameterType) is not available "
                             f"for commands of the section command interface ('{group_val}')")
                check15_ok = False
    if check15_ok and cmd_count > 0:
        report_ok(f"15. Commands: {cmd_count} command(s), groups valid")

# ── Check 16a (local): a type spelled with an export folder name ──
# cfg:Catalogs.X is the directory of the dump, not a type; the platform refuses it.
# Checked without a configuration directory: the spelling is wrong on its own.

folder_type_values = {}
for tn in find_all(root, ".//v8:Type | .//v8:TypeSet"):
    tv = inner_text(tn).strip()
    if not tv:
        continue
    bare = tv.split(":", 1)[1] if ":" in tv else tv
    head_seg = bare.split(".", 1)[0]
    if "." in bare and head_seg in export_folder_types:
        folder_type_values[tv] = head_seg
for tv in sorted(folder_type_values):
    head_seg = folder_type_values[tv]
    ref_kind = export_folder_types[head_seg]
    hint = f" — a reference type is '{ref_kind}.<Name>'" if ref_kind else ""
    report_error(f"16a. Type '{tv}' uses the export folder name '{head_seg}' instead of a type{hint}")

# ── Состав конфигурации (ChildObjects из Configuration.xml) ──
# Платформа судит о существовании объекта по СОСТАВУ, а не по наличию файла. Файла может не быть
# в частичной выгрузке: такой фрагмент грузится через /LoadConfigFromFiles -listFile слиянием с базой,
# и ссылка на невыгруженный объект остаётся рабочей. Отсюда два разных исхода:
#   нет в составе        -> платформа отвергнет загрузку всегда -> ERROR
#   в составе, файла нет -> полная загрузка упадёт, частичная пройдёт -> WARN
# ChildObjects конфигурации — плоский список <Вид>Имя</Вид>, поэтому ищем подстроку в границах секции
# без копирования и без разбора XML. Кэш живёт только в пределах одного объекта: в batch-режиме
# каждый следующий разбирается заново (в py — новый процесс, в PS — новая область видимости скрипта),
# так что полная карта (~100 мс) оплачивалась бы каждым объектом.

_cfg_text = None
_cfg_child_lower = None
_cfg_child_start = -1
_cfg_child_end = -1
_cfg_text_loaded = False


def _init_config_text():
    global _cfg_text, _cfg_child_start, _cfg_child_end, _cfg_text_loaded
    if _cfg_text_loaded:
        return
    _cfg_text_loaded = True
    if not config_dir:
        return
    cfg_path = os.path.join(config_dir, "Configuration.xml")
    if not os.path.exists(cfg_path):
        return
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            _cfg_text = f.read()
    except Exception:
        _cfg_text = None
        return
    s = _cfg_text.find("<ChildObjects>")
    e = _cfg_text.rfind("</ChildObjects>")
    if s >= 0 and e > s:
        _cfg_child_start = s
        _cfg_child_end = e


def config_is_extension():
    _init_config_text()
    return bool(_cfg_text) and "ConfigurationExtensionPurpose" in _cfg_text


def in_config_composition(kind, name):
    """True — объект есть в составе; False — нет; None — состав неизвестен
    (нет Configuration.xml или в нём нет ChildObjects), тогда вызывающий оставляет мягкий уровень."""
    global _cfg_child_lower
    _init_config_text()
    if _cfg_child_start < 0:
        return None
    needle = "<{0}>{1}</{0}>".format(kind, name)
    if _cfg_text.find(needle, _cfg_child_start, _cfg_child_end) >= 0:
        return True
    # Промах по точному совпадению — сверяем без учёта регистра, как это делает платформа.
    # Порядок именно такой: точный поиск на порядок дешевле, а промахи редки. Нижний регистр
    # берём от СРЕЗА и проверяем факт вхождения: смещения в lower() совпадать с оригиналом не обязаны.
    if _cfg_child_lower is None:
        _cfg_child_lower = _cfg_text[_cfg_child_start:_cfg_child_end].lower()
    return needle.lower() in _cfg_child_lower

# ── Check 16: Reference type existence — типы вида CatalogRef.X должны разрешаться в объекты конфигурации ──
# Уровень выбирается по составу конфигурации: типа нет в ChildObjects — «Неизвестное имя типа» при
# загрузке (ERROR); объект в составе есть, а файла в выгрузке нет — частичная выгрузка (WARN).
# Расширения (CFE) пропускаем — их типы ссылаются на объекты базовой конфигурации, которых в выгрузке
# расширения нет.

if config_dir:
    is_extension = config_is_extension()
    if not is_extension:
        ref_dir_map = {
            "CatalogRef": "Catalogs", "DocumentRef": "Documents", "EnumRef": "Enums",
            "ChartOfAccountsRef": "ChartsOfAccounts", "ChartOfCharacteristicTypesRef": "ChartsOfCharacteristicTypes",
            "ChartOfCalculationTypesRef": "ChartsOfCalculationTypes", "BusinessProcessRef": "BusinessProcesses",
            "ExchangePlanRef": "ExchangePlans", "TaskRef": "Tasks", "DefinedType": "DefinedTypes",
        }
        checked_refs = {}   # ref_key -> найден ли; для условия OK
        missing_refs = {}   # ref_key -> ref_dir; объект есть в составе, файла в выгрузке нет
        absent_refs = {}    # ref_key -> ref_dir; объекта нет в составе конфигурации
        unknown_refs = {}   # ref_key -> ref_dir; состав неизвестен (Configuration.xml без ChildObjects)
        for tn in find_all(root, ".//v8:Type"):
            tv = inner_text(tn).strip()
            if not tv:
                continue
            colon_idx = tv.find(":")
            if colon_idx >= 0:
                tv = tv[colon_idx + 1:]
            dot_idx = tv.find(".")
            if dot_idx < 0:
                continue
            ref_cat = tv[:dot_idx]
            ref_name = tv[dot_idx + 1:]
            ref_dir = ref_dir_map.get(ref_cat)
            if not ref_dir or not ref_name:
                continue
            ref_key = f"{ref_cat}.{ref_name}"
            if ref_key in checked_refs:
                continue
            ref_folder = os.path.join(config_dir, ref_dir, ref_name)
            ref_file = os.path.join(config_dir, ref_dir, ref_name + ".xml")
            if os.path.exists(ref_folder) or os.path.exists(ref_file):
                checked_refs[ref_key] = True
            else:
                checked_refs[ref_key] = False
                # Вид метаданных в ChildObjects — это тип без суффикса Ref (CatalogRef -> Catalog);
                # DefinedType суффикса не имеет и пишется в состав как есть.
                ref_kind_tag = ref_cat[:-3] if ref_cat.endswith("Ref") else ref_cat
                in_composition = in_config_composition(ref_kind_tag, ref_name)
                if in_composition is False:
                    absent_refs[ref_key] = ref_dir
                elif in_composition is True:
                    missing_refs[ref_key] = ref_dir
                else:
                    unknown_refs[ref_key] = ref_dir
        for ak in sorted(absent_refs):
            report_error(f"16. Reference type '{ak}' — the object is not in the configuration ({absent_refs[ak]}/) — «Неизвестное имя типа» on load")
        for mk in sorted(missing_refs):
            report_warn(f"16. Reference type '{mk}' — the object is in the configuration, but its file is not in the dump ({missing_refs[mk]}/)")
        for uk in sorted(unknown_refs):
            report_warn(f"16. Reference type '{uk}' not found in the configuration ({unknown_refs[uk]}/)")
        if not absent_refs and not missing_refs and not unknown_refs and checked_refs:
            report_ok(f"16. Reference types: {len(checked_refs)} resolved")

# ── Check 22: имя типа — грамматика (уровень 1) и словарь по контексту владельца (уровень 2) ──
# УРОВЕНЬ 1 не зависит ни от версии платформы, ни от состава конфигурации: содержимое <v8:Type>
# всегда несёт префикс пространства имён (xs:/v8:/cfg:/dNpM:/ent:/…). Голое имя платформа не примет
# никогда — так выглядит и тип СУБД («varchar(150)»), и опечатка («Srting(20)»).
# УРОВЕНЬ 2 — словарь: у хранимого объекта набор типов у́же, чем у обработки или отчёта, где
# доступны ТаблицаЗначений, ОписаниеТипов, Картинка и прочие рантайм-типы. Здесь только
# предупреждение: список конечен, но пополняется с версиями платформы.
KNOWN_XS_TYPES = {"xs:string", "xs:decimal", "xs:boolean", "xs:dateTime", "xs:base64Binary"}
KNOWN_V8_TYPES = {
    "ValueStorage", "UUID", "Null", "Type", "ValueTable", "ValueTree", "ValueList",
    "ValueListType", "StandardPeriod", "StandardBeginningDate", "PointInTime", "TypeDescription",
    "FixedArray", "FixedMap", "FixedStructure", "FillChecking", "Universal",
}
# Ссылочные метатипы: с именем объекта (<Метатип>.<Имя>) — конкретный тип, без имени — множество.
REF_META_TYPES = {
    "CatalogRef", "DocumentRef", "EnumRef", "ChartOfAccountsRef",
    "ChartOfCharacteristicTypesRef", "ChartOfCalculationTypesRef", "ExchangePlanRef",
    "BusinessProcessRef", "BusinessProcessRoutePointRef", "TaskRef", "AnyRef", "AnyIBRef",
}
# Прочие имена пространства current-config без точки — платформенные, состав конфигурации их не меняет.
CFG_BARE_NAMES = {"ConstantsSet", "ReportBuilder", "FilterCriterion", "DynamicList"}
# Виды, чьи реквизиты ХРАНЯТСЯ в базе: там рантайм-типы недопустимы. У обработки и отчёта — наоборот.
STORED_OWNER_TYPES = {
    "Catalog", "Document", "DocumentJournal", "InformationRegister", "AccumulationRegister",
    "AccountingRegister", "CalculationRegister", "ChartOfAccounts", "ChartOfCharacteristicTypes",
    "ChartOfCalculationTypes", "ExchangePlan", "BusinessProcess", "Task", "Constant", "Table",
}
ATTR_TYPE_HOLDERS = {
    "Attribute", "Dimension", "Resource", "Column", "Field", "AddressingAttribute",
    "AccountingFlag", "ExtDimensionAccountingFlag",
}


def _is_storable_type(t):
    if t in KNOWN_XS_TYPES:
        return True
    if t in ("v8:ValueStorage", "v8:UUID", "v8:Null"):
        return True
    m = re.match(r"^(?:cfg|d\d+p\d+):(.+)$", t)
    if not m:
        return False
    name = m.group(1)
    base = name.split(".", 1)[0]
    if base in REF_META_TYPES:
        return True
    return base in ("DefinedType", "Characteristic", "ExternalDataSourceTableRef")


type_nodes_22 = root.findall(".//v8:Type", NS) + root.findall(".//v8:TypeSet", NS)
bad_grammar = {}
unknown_vocab = {}
not_storable = {}
types_seen = 0
for tn in type_nodes_22:
    t = (tn.text or "").strip()
    if not t:
        continue
    types_seen += 1
    # Local: an export folder name in place of a type is reported once, by 16a.
    if t in folder_type_values:
        continue
    if ":" not in t:
        bad_grammar[t] = True
        continue
    prefix, local = t.split(":", 1)
    if prefix == "xs":
        if t not in KNOWN_XS_TYPES:
            unknown_vocab[t] = True
    elif prefix == "v8":
        if local not in KNOWN_V8_TYPES:
            unknown_vocab[t] = True
    elif prefix == "cfg" or re.match(r"^d\d+p\d+$", prefix):
        # Имя объекта конфигурации проверяет Check 16; здесь — только форма и платформенная часть.
        if "." not in local:
            if (local not in REF_META_TYPES and local not in CFG_BARE_NAMES
                    and not re.match(r"^[A-Za-z][A-Za-z0-9]*(Object|Manager|List|Selection|RecordSet|RecordKey|RecordManager)$", local)):
                unknown_vocab[t] = True
        elif not re.match(r"^[A-Za-z][A-Za-z0-9]*\.[^.]+(\.[^.]+)?$", local):
            bad_grammar[t] = True
    # Прочие пространства (ent:, v8ui:, dcs*:, mxl: …) — форму имени не навязываем: там свои словари.

    if md_type in STORED_OWNER_TYPES:
        owner = tn.getparent()                                  # <Type>
        props = owner.getparent() if owner is not None else None   # <Properties>
        child = props.getparent() if props is not None else None   # <Attribute>/<Field>/…
        if child is not None and etree.QName(child).localname in ATTR_TYPE_HOLDERS and not _is_storable_type(t):
            not_storable[t] = etree.QName(child).localname

for bk in sorted(bad_grammar):
    report_error(f"22. Type '{bk}' — not a platform type name: the namespace prefix is missing or "
                 "the reference type form is wrong. On load: «Неизвестное имя типа»")
for nk in sorted(not_storable):
    report_warn(f"22. Type '{nk}' on element {not_storable[nk]} of object {md_type}: such types "
                "occur on attributes of data processors and reports, but not of objects stored in the infobase")
for uk in sorted(unknown_vocab):
    report_warn(f"22. Type '{uk}' is not in the list of known platform types — check the spelling "
                "(the list grows with platform versions)")
if not bad_grammar and not not_storable and not unknown_vocab and types_seen:
    report_ok(f"22. Type names: {types_seen} checked")

# ── Check 23: тип-множество там, где его не принимают ──
# Три уровня строгости, все замерены загрузкой в базу на 8.3.24.1691:
#  ERROR — множество в составе определяемого типа: платформа отвергает файл целиком
#          («ОпределяемыйТип.<Имя> - Недопустимый тип»), проверено на ОпределяемыйТип,
#          Характеристика, ЛюбаяСсылка и голых ссылках;
#  WARN  — голый метатип в типе значения ПВХ: загрузка проходит, но Конфигуратор такой тип не
#          предлагает (в дереве выбора это папка без флажка), а ЛюбаяСсылка на выгрузке
#          возвращается как ЛюбаяСсылкаИБ;
#  WARN  — определяемый тип или характеристика одним из составного: Конфигуратор даёт
#          выбрать их только единственными (характеристику — даже с другой характеристикой). В корпусе erp+acc 6500 единственных против 1 составного — и этот один
#          лежит в типовой ERP (Документ.НачислениеИСписаниеБонусныхБаллов.Баллы), поэтому не ошибка.
dt_sets_seen = 0
dt_sets_bad = False
for tb in root.xpath("//md:Type | //md:ValueType", namespaces=NS):
    sets = tb.xpath("v8:TypeSet", namespaces=NS)
    if not sets:
        continue
    dt_sets_seen += 1
    members = len(tb.xpath("v8:Type", namespaces=NS)) + len(sets)
    owner = tb.getparent().getparent()
    owner_kind = etree.QName(owner.tag).localname if owner is not None else ""
    for st in sets:
        raw = re.sub(r'^(?:cfg|d\d+p\d+):', '', (st.text or "").strip())
        if owner_kind == "DefinedType":
            dt_sets_bad = True
            report_error(f"23. Defined type '{obj_name}': contains the type set '{raw}' — the platform will not load such a file («Недопустимый тип»). A defined type may contain only concrete types")
            continue
        if owner_kind == "ChartOfCharacteristicTypes" and not re.match(r'^DefinedType[.]', raw):
            dt_sets_bad = True
            report_warn(f"23. Chart of characteristic types '{obj_name}': value type '{raw}' is not offered by Designer (in the type picker it is a folder without a checkbox); AnyRef comes back as AnyIBRef on dump")
        if members > 1 and re.match(r'^(DefinedType|Characteristic)[.]', raw):
            dt_sets_bad = True
            report_warn(f"23. Composite type contains '{raw}' — Designer allows a defined type or a characteristic only as the sole type; the platform loads it")
if dt_sets_seen and not dt_sets_bad:
    report_ok(f"23. Type sets: {dt_sets_seen} block(s) checked")

# ── Check 18: свойства, появившиеся в новых версиях формата ──
# Реестр «тег → минимальная версия формата». Служит двум целям: (1) поймать свойство в файле со
# слишком старым штампом — при сборке на старой платформе оно будет молча отброшено (платформа
# рапортует успех, а свойство теряется); (2) подсказать, что конструкция требует более нового
# формата. Расширяется одной строкой на свойство — задел под 2.21 (8.5) и последующие.
versioned_props = {
    "TypeReductionMode": "2.18",   # режим приведения типов (стандартные реквизиты, измерения РС)
    "LineNumberLength": "2.20",    # длина номера строки ТЧ (5..9)
    # 2.21 (8.5): подтверждено синтетикой — одни исходники, выгрузка с 8.3.27 и с 8.5.1.
    "Color": "2.21",                            # цвет значения перечисления
    "AuxiliaryVariantForm": "2.21",             # вспомогательная форма варианта отчёта
    "UseInInterfaceCompatibilityMode": "2.21",  # использование общей формы в режиме совместимости интерфейса
}

file_rank = version_rank
if file_rank > 0:
    for vp in sorted(versioned_props):
        nodes = find_all(root, f"//md:{vp} | //xr:{vp}")
        if nodes and file_rank < format_rank(versioned_props[vp]):
            report_error(f"18. <{vp}> appeared in format {versioned_props[vp]}, but the file declares {version} — the platform of that version drops the property on load")

# ── Check 19: LineNumberLength — допустимый диапазон 5..9 ──
# Длина номера строки ТЧ: 5 (до 99 999 строк) … 9 (до 999 999 999). Границы — из документации 1С.
for lnl in find_all(root, "//md:LineNumberLength"):
    raw = inner_text(lnl).strip()
    if not re.match(r'^\d+$', raw):
        report_error(f"19. LineNumberLength='{raw}' — must be an integer 5..9")
    elif int(raw) < 5 or int(raw) > 9:
        report_error(f"19. LineNumberLength={raw} is out of range 5..9")

# ── Check 25: многоязычная строка (LocalStringType) — только элементы v8:item, без простого текста ──
# Простой текст в таком теге платформа не загружает: «Ошибка преобразования данных XDTO … LocalStringType».
local_string_tags = ['Synonym', 'ToolTip', 'Explanation', 'ObjectPresentation', 'ExtendedObjectPresentation', 'ListPresentation',
                     'ExtendedListPresentation', 'RecordPresentation', 'ExtendedRecordPresentation', 'ExtendedPresentation', 'Format', 'EditFormat']
for ls in find_all(root, '|'.join(f"//md:{t}|//xr:{t}" for t in local_string_tags)):
    plain = ((ls.text or '') + ''.join(ch.tail or '' for ch in ls)).strip()
    if not plain:
        continue
    owner = find_all(ls.getparent(), "md:Name|xr:Name")
    owner_name = inner_text(owner[0]).strip() if owner else ''
    where = f" of '{owner_name}'" if owner_name and owner_name != obj_name else ''
    report_error(f"25. <{local_name(ls)}>{where} holds plain text '{plain}' — a multilingual string needs <v8:item> elements; the platform rejects the load")

# ── Check 17: MDObjectRef form — ссылка на ОБЪЕКТ метаданных, а не на тип ссылки ──
# Owners/BasedOn/RegisterRecords/RegisteredDocuments/References содержат путь вида "Catalog.Валюты".
# "CatalogRef.Валюты" — частая ошибка (тип ссылки вместо объекта): платформа отвечает
# «Неизвестный объект метаданных». Вида метаданных, оканчивающегося на Ref, не существует → ERROR.
# Неизвестный первый сегмент без Ref — только WARN (список видов может быть неполон).

md_ref_nodes = find_all(root, "//*[@xsi:type='xr:MDObjectRef']")
if md_ref_nodes:
    known_roots = tuple(valid_types) + tuple(structural_only_types)
    bad_ref_form = {}    # значение -> True (ссылочная форма, гарантированно нерабочая)
    unknown_root = {}    # значение -> корень
    for rn in md_ref_nodes:
        rv = inner_text(rn).strip()
        if not rv:
            continue
        rroot = rv.split('.')[0]
        if rroot in known_roots:
            continue
        if rroot.endswith('Ref'):
            bad_ref_form[rv] = True
        else:
            unknown_root[rv] = rroot
    for bk in sorted(bad_ref_form):
        fixed = re.sub(r'^([A-Za-z]+)Ref\.', r'\1.', bk)
        report_error(f"17. MDObjectRef '{bk}' — refers to a TYPE, not to a metadata object; should be '{fixed}' (otherwise «Неизвестный объект метаданных» on load)")
    for uk in sorted(unknown_root):
        report_warn(f"17. MDObjectRef '{uk}' — unknown metadata kind '{unknown_root[uk]}' (typo?)")
    if not bad_ref_form and not unknown_root:
        report_ok(f"17. MDObjectRef form: {len(md_ref_nodes)} checked")

# ── Check 20: Default*Form / Auxiliary*Form / ChoiceForm — ссылка на существующую форму ──
# Платформа отвергает загрузку: «Неизвестный объект метаданных - Catalog.Товары.Form.НетТакойФормы».
# Две формы записи: "CommonForm.Имя" и "<Вид>.<Объект>.Form.<Форма>", причём объект может быть чужим
# (DefaultChoiceForm документа указывает на форму журнала документов). Для СВОЕГО объекта проверяем
# регистрацию формы в ChildObjects — работает и на одиночном файле; для чужого и общей формы нужна
# конфигурация. Заимствованные объекты расширения (ObjectBelonging=Adopted) пропускаем: их формы
# живут в основной конфигурации, в выгрузке расширения их нет.
#
# Уровень везде выбирается по составу, а не по наличию файла (см. in_config_composition):
# нет в ChildObjects — платформа откажет и при полной, и при частичной загрузке (ERROR);
# в составе есть, а файла в выгрузке нет — это фрагмент частичной выгрузки, и загрузится он или нет,
# зависит от состояния конфигурации БД, которого валидатору не видно (WARN).

form_owner_dir_map = {
    "Catalog": "Catalogs", "Document": "Documents", "DocumentJournal": "DocumentJournals",
    "Enum": "Enums", "Report": "Reports", "DataProcessor": "DataProcessors",
    "InformationRegister": "InformationRegisters", "AccumulationRegister": "AccumulationRegisters",
    "AccountingRegister": "AccountingRegisters", "CalculationRegister": "CalculationRegisters",
    "ChartOfAccounts": "ChartsOfAccounts", "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
    "ChartOfCalculationTypes": "ChartsOfCalculationTypes", "BusinessProcess": "BusinessProcesses",
    "Task": "Tasks", "ExchangePlan": "ExchangePlans", "SettingsStorage": "SettingsStorages",
    "FilterCriterion": "FilterCriteria", "ExternalDataSource": "ExternalDataSources",
}

_belonging_node = find(type_node, "md:Properties/md:ObjectBelonging")
is_adopted = _belonging_node is not None and inner_text(_belonging_node).strip() == "Adopted"

GUID_RE_20 = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
TAG_RE_20 = re.compile(r'^(Default|Auxiliary)[A-Za-z]*Form$')


def _form_file_exists_20(base_dir, form_name):
    forms_dir = os.path.join(base_dir, "Forms")
    return (os.path.exists(os.path.join(forms_dir, form_name + ".xml"))
            or os.path.exists(os.path.join(forms_dir, form_name, "Form.xml"))
            or os.path.exists(os.path.join(forms_dir, form_name, "Ext", "Form.xml")))


if not is_adopted:
    is_extension_20 = config_is_extension()

    # формы своего объекта: имена из ChildObjects (сравнение регистронезависимое — как у платформы)
    own_forms = {}
    if child_obj_node is not None:
        for child in child_obj_node:
            if isinstance(child.tag, str) and local_name(child) == "Form":
                # Local: an inline descriptor (6a) is counted by its declared name, not by its text.
                inline_name_20 = find(child, "md:Properties/md:Name")
                fn = (inner_text(inline_name_20) if inline_name_20 is not None else inner_text(child)).strip()
                if fn:
                    own_forms[fn.lower()] = fn
    own_dir = os.path.join(os.path.dirname(resolved_path), obj_name)

    form_refs_checked = 0
    form_ref_bad = False
    for frn in root.iter():
        if not isinstance(frn.tag, str):
            continue
        tag = local_name(frn)
        # ChoiceForm — «форма выбора» реквизита, ссылка того же вида, что и Default*Form.
        if not TAG_RE_20.match(tag) and tag != "ChoiceForm":
            continue
        ref = inner_text(frn).strip()
        if not ref:
            continue
        # Значением бывает GUID (erp: Report.СверкаДанныхОУиБУ, DefaultVariantForm) — проверить
        # его без обхода всех форм нельзя; cf-validate (Check 9) такие тоже пропускает.
        if GUID_RE_20.match(ref):
            continue
        parts = ref.split(".")
        form_refs_checked += 1

        if len(parts) == 2 and parts[0] == "CommonForm":
            if is_extension_20 or not config_dir:
                continue
            cf_dir = os.path.join(config_dir, "CommonForms", parts[1])
            cf_ok = (os.path.exists(cf_dir + ".xml")
                     or os.path.exists(os.path.join(cf_dir, "Ext", "Form.xml"))
                     or os.path.exists(os.path.join(cf_dir, "Form.xml")))
            if not cf_ok:
                if in_config_composition("CommonForm", parts[1]) is True:
                    report_warn(f"20. {tag} '{ref}' — the common form is in the configuration, "
                                f"but the form file is not in the dump (CommonForms/{parts[1]})")
                else:
                    report_error(f"20. {tag} '{ref}' — the common form is not in the configuration "
                                 f"(CommonForms/{parts[1]}) — «Неизвестный объект метаданных» on load")
                    form_ref_bad = True
            continue

        # Ссылка на форму таблицы внешнего источника — шестичастная:
        # ExternalDataSource.<Источник>.Table.<Таблица>.Form.<Форма>. Сводим её к четырём частям
        # (вид = Table, объект = имя таблицы), дальше проверка общая.
        if (len(parts) == 6 and parts[0] == "ExternalDataSource"
                and parts[2] == "Table" and parts[4] == "Form"):
            parts = ["Table", parts[3], "Form", parts[5]]

        if len(parts) != 4 or parts[2] != "Form":
            report_warn(f"20. {tag} '{ref}' — unexpected form reference shape "
                        f"(expected 'CommonForm.<Name>' or '<Kind>.<Object>.Form.<Form>')")
            continue

        ref_kind, ref_obj, ref_form = parts[0], parts[1], parts[3]

        if ref_kind.lower() == md_type.lower() and ref_obj.lower() == obj_name.lower():
            if ref_form.lower() not in own_forms:
                known = ", ".join(sorted(own_forms.values())) if own_forms else "no forms"
                report_error(f"20. {tag} '{ref}' — form '{ref_form}' is not registered in "
                             f"the object's ChildObjects (present: {known}) — «Неизвестный объект метаданных» on load")
                form_ref_bad = True
            # Local: a registered form without its descriptor file is check 6b (always an ERROR).
            continue

        # чужой объект (например журнал документов) — нужна конфигурация
        if is_extension_20 or not config_dir:
            continue
        ref_dir_20 = form_owner_dir_map.get(ref_kind)
        if not ref_dir_20:
            report_warn(f"20. {tag} '{ref}' — unknown metadata kind '{ref_kind}' (typo?)")
            continue
        ref_obj_xml = os.path.join(config_dir, ref_dir_20, ref_obj + ".xml")
        if not os.path.exists(ref_obj_xml):
            obj_in_composition = in_config_composition(ref_kind, ref_obj)
            if obj_in_composition is False:
                report_error(f"20. {tag} '{ref}' — object '{ref_kind}.{ref_obj}' is not in the "
                             f"configuration ({ref_dir_20}/) — «Неизвестный объект метаданных» on load")
                form_ref_bad = True
            elif obj_in_composition is True:
                report_warn(f"20. {tag} '{ref}' — object '{ref_kind}.{ref_obj}' is in the "
                            f"configuration, but its file is not in the dump ({ref_dir_20}/)")
            else:
                report_warn(f"20. {tag} '{ref}' — object '{ref_kind}.{ref_obj}' not found in the configuration ({ref_dir_20}/)")
            continue
        if not _form_file_exists_20(os.path.join(config_dir, ref_dir_20, ref_obj), ref_form):
            report_error(f"20. {tag} '{ref}' — form '{ref_form}' not found on object "
                         f"'{ref_kind}.{ref_obj}' — «Неизвестный объект метаданных» on load")
            form_ref_bad = True

    if form_refs_checked > 0 and not form_ref_bad:
        report_ok(f"20. Form refs: {form_refs_checked} resolved")

# ── Check 21: таблица внешнего источника — ссылки на поля и наличие ключа ──
# Свойства таблицы ссылаются на её же поля полным путём. Опечатка в имени поля даёт
# «Неизвестный объект метаданных» при загрузке, а найти её глазами в шестичастном пути трудно.
if md_type == "Table":
    field_names = set()
    if child_obj_node is not None:
        for f in find_all(child_obj_node, "md:Field/md:Properties/md:Name"):
            field_names.add(inner_text(f))
    eds_refs_checked = 0
    eds_refs_bad = False
    for tag, is_list in (("KeyFields", True), ("InputByString", True), ("DataLockFields", True),
                         ("PresentationField", False), ("ParentField", False), ("DataVersionField", False)):
        if is_list:
            refs = [inner_text(n) for n in find_all(props_node, f"md:{tag}/xr:Field")]
        else:
            n = find(props_node, f"md:{tag}")
            refs = [inner_text(n)] if n is not None and inner_text(n) else []
        for ref in refs:
            eds_refs_checked += 1
            parts = ref.split(".")
            # Ожидается ExternalDataSource.<Источник>.Table.<Таблица>.Field.<Поле>
            if len(parts) != 6 or parts[0] != "ExternalDataSource" or parts[2] != "Table" or parts[4] != "Field":
                report_error(f"21. {tag} '{ref}' — expected ExternalDataSource.<Source>.Table.<Table>.Field.<Field>")
                eds_refs_bad = True
                continue
            if parts[3] != obj_name:
                report_error(f"21. {tag} '{ref}' — refers to a field of ANOTHER table (this one: {obj_name})")
                eds_refs_bad = True
                continue
            if parts[5] not in field_names:
                known = ", ".join(sorted(field_names)) if field_names else "no fields"
                report_error(f"21. {tag} '{ref}' — field '{parts[5]}' is not in the table (present: {known})")
                eds_refs_bad = True
    if eds_refs_checked > 0 and not eds_refs_bad:
        report_ok(f"21. Field refs: {eds_refs_checked} resolved")

    # Ключ: загрузка XML таблицу без ключа принимает (проверено на платформе), а Конфигуратор
    # интерактивно требует. Отсюда предупреждение, а не ошибка: рабочие конфигурации без ключа есть.
    if not find_all(props_node, "md:KeyFields/xr:Field"):
        report_warn("21. KeyFields is empty — the platform loads such a table, but the record form and the record set will be unavailable")


# ── Final output ──────────────────────────────────────────────

finalize()

if errors > 0:
    sys.exit(1)
sys.exit(0)
