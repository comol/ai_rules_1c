"""Объект по пути формы в выгрузке и путь формы для шапки досье."""

import pathlib


def _display_path(form_path, config_dir):
    path = pathlib.Path(form_path).resolve()
    if config_dir:
        try:
            return path.relative_to(pathlib.Path(config_dir).resolve()).as_posix()
        except ValueError:
            pass
    key = _meta_key(path)
    return "/".join(key) if key else "/".join(path.parts[-3:])


METADATA_DIRS = frozenset({"Catalogs", "Documents", "DataProcessors", "Reports", "CommonForms", "InformationRegisters", "AccumulationRegisters",
                           "AccountingRegisters", "CalculationRegisters", "ExchangePlans", "ChartsOfCharacteristicTypes", "ChartsOfAccounts",
                           "ChartsOfCalculationTypes", "BusinessProcesses", "Tasks", "Enums", "Constants", "DocumentJournals", "SettingsStorages",
                           "FilterCriteria", "CommonCommands", "WebServices", "HTTPServices"})


OBJECT_KINDS = {"Catalogs": "Справочник", "Documents": "Документ", "DataProcessors": "Обработка", "Reports": "Отчёт",
                "InformationRegisters": "РегистрСведений", "AccumulationRegisters": "РегистрНакопления", "ExchangePlans": "ПланОбмена",
                "ChartsOfCharacteristicTypes": "ПланВидовХарактеристик", "ChartsOfAccounts": "ПланСчетов", "Enums": "Перечисление",
                "BusinessProcesses": "БизнесПроцесс", "Tasks": "Задача", "DocumentJournals": "ЖурналДокументов"}


def _object_by_path(form_path):
    """Объект формы по её месту в выгрузке (`Catalogs/Номенклатура/Forms/…` → `Справочник.Номенклатура`) либо `None`: без выгрузки это
    единственное, что говорит об объекте."""
    key = _meta_key(pathlib.Path(form_path).resolve().parent)
    if key is None or key[0] not in OBJECT_KINDS:          # у общей формы объекта нет
        return None
    return f"{OBJECT_KINDS[key[0]]}.{key[1]}"


def config_of(form_path):
    """Выгрузка конфигурации — каталог, в котором лежит форма (`<выгрузка>/Catalogs/<Имя>/Forms/…`), либо `None`: форма вне выгрузки."""
    parts = pathlib.Path(form_path).resolve().parts
    for at in range(len(parts) - 1, 0, -1):
        after = parts[at + 2:at + 3]
        if parts[at] in METADATA_DIRS and (after == ("Forms",) or (parts[at] == "CommonForms" and after == ("Ext",))):
            return pathlib.Path(*parts[:at])
    return None


def _inside(path, root):
    try:
        pathlib.Path(path).resolve().relative_to(pathlib.Path(root).resolve())
        return True
    except ValueError:
        return False


def _meta_key(path):
    """Путь формы от каталога вида объекта (`Catalogs/Номенклатура/Forms/…`, `CommonForms/Имя/Ext/…`) либо `None`: выгрузка и копия формы вне
    её — одна форма."""
    parts = pathlib.Path(path).resolve().parts
    for at in range(len(parts) - 1, -1, -1):        # справа: каталог выгрузки сам может лежать под каталогом с таким именем («Documents»)
        after = parts[at + 2:at + 3]
        if parts[at] in METADATA_DIRS and (after == ("Forms",) or (parts[at] == "CommonForms" and after == ("Ext",))):
            return parts[at:]
    return None
