# cf-edit — справочник операций

## modify-property

Свойства для редактирования:

### Скалярные
`Name`, `Version`, `Vendor`, `Comment`, `NamePrefix`, `UpdateCatalogAddress`

### LocalString (многоязычные)
`Synonym`, `BriefInformation`, `DetailedInformation`, `Copyright`, `VendorInformationAddress`, `ConfigurationInformationAddress`

### Enum
| Свойство | Допустимые значения |
|----------|---------------------|
| `CompatibilityMode` | `Version8_3_20` ... `Version8_3_28`, `Version8_5_1`, `DontUse` |
| `ConfigurationExtensionCompatibilityMode` | то же |
| `DefaultRunMode` | `ManagedApplication`, `OrdinaryApplication`, `Auto` |
| `ScriptVariant` | `Russian`, `English` |
| `DataLockControlMode` | `Managed`, `Automatic`, `AutomaticAndManaged` |
| `ObjectAutonumerationMode` | `NotAutoFree`, `AutoFree` |
| `ModalityUseMode` | `DontUse`, `Use`, `UseWithWarnings` |
| `SynchronousPlatformExtensionAndAddInCallUseMode` | `DontUse`, `Use`, `UseWithWarnings` |
| `InterfaceCompatibilityMode` | `Version8_2`, `Version8_2EnableTaxi`, `Taxi`, `TaxiEnableVersion8_2`, `TaxiEnableVersion8_5`, `Version8_5EnableTaxi`, `Version8_5` |
| `DatabaseTablespacesUseMode` | `DontUse`, `Use` |
| `MainClientApplicationWindowMode` | `Normal`, `Fullscreen`, `Kiosk` |

### Ref
`DefaultLanguage` — значение вида `Language.Русский`

### Формат batch
`"Version=1.0.0.1 ;; Vendor=Фирма 1С ;; Synonym=Тестовая конфигурация"`

## add-childObject / remove-childObject

Формат: `Type.Name` — XML-тип и имя объекта через точку.

При добавлении объект вставляется в каноническую позицию:
1. Находит последний элемент того же типа → вставляет после
2. Если тип отсутствует → находит последний элемент предшествующего типа → вставляет после
3. Внутри одного типа — алфавитный порядок

Batch: `"Catalog.Товары ;; Document.Заказ ;; Enum.ВидыОплат"`

## add-defaultRole / remove-defaultRole / set-defaultRoles

Имя роли: `ПолныеПрава` или `Role.ПолныеПрава` (префикс `Role.` добавляется автоматически).

`set-defaultRoles` полностью заменяет список ролей.

## DefinitionFile (JSON)

```json
[
  { "operation": "modify-property", "value": "Version=2.0.0.1 ;; Vendor=Test" },
  { "operation": "add-childObject", "value": "Catalog.Товары ;; Document.Заказ" },
  { "operation": "add-defaultRole", "value": "ПолныеПрава" }
]
```

## Авто-валидация

После сохранения автоматически запускается `cf-validate` (если не указан `-NoValidate`).
