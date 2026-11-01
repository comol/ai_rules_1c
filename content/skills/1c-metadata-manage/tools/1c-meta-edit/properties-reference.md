# Свойства объекта и свойства-списки

Справочник операций для обычных свойств объекта и свойств-списков (Owners, RegisterRecords, BasedOn, InputByString).

## modify-property

Изменение свойств объекта по имени свойства 1С (PascalCase, как в конфигураторе). Формат: `Ключ=Значение`
(batch через `;;`):
```powershell
-Operation modify-property -Value "CodeLength=11 ;; DescriptionLength=150"
-Operation modify-property -Value "Hierarchical=true"
```

Свойство можно задать, даже если оно ещё не выставлено у объекта (например `FullTextSearch`, `DataHistory`).
Опечатка в имени свойства → ошибка (правка не теряется молча). Допустимы имена свойств соответствующего типа объекта.

- **Перечисления.** Значение свойства-перечисления (`RegisterType`, `CodeAllowedLength`, `DataLockControlMode`, …)
  приводится к канону: алиас (`обороты` → `Turnovers`) и регистр исправляются молча, неизвестное
  значение — ошибка со списком допустимых до записи файла.
- **Регистр ключа.** `codeallowedlength=Fixed` пишет тег `<CodeAllowedLength>`, а не ключ как подан.
- **Многоязычные свойства** (`Synonym`, `ToolTip`, `Explanation`, `ObjectPresentation`, `ListPresentation`,
  `ExtendedObjectPresentation`, `ExtendedListPresentation`, `RecordPresentation`, `ExtendedRecordPresentation`,
  `ExtendedPresentation`, `Format`, `EditFormat`) пишутся элементами `v8:item`, узел заменяется целиком.
  Inline-строка — значение для `ru`; в JSON можно `{ "ru": "…", "en": "…" }`.
- **Нулевая длина кода / номера.** `CodeLength=0` / `NumberLength=0` убирает `StandardAttribute.Code` /
  `StandardAttribute.Number` из `InputByString`: поле нулевой длины во вводе по строке платформа не загружает.

### Type — тип значения (Константа, ПВХ)

`Type=...` перестраивает дескриптор типа значения. Значение — тип 1С в том же синтаксисе,
что у реквизитов: составной через `+`, с квалификаторами и ссылочными типами:
```powershell
-Operation modify-property -Value "Type=String(100) + Number(15,2) + CatalogRef.Номенклатура"
```
Структурные свойства (со вложенными узлами) в скалярный текст не превращаются: попытка задать
такое свойство обычным `Ключ=Значение` (кроме `Type` и многоязычных свойств) завершается ошибкой до записи файла.

## Свойства-списки

Свойства, значение которых — список ссылок. Управляются через inline `add-*` / `remove-*` / `set-*` и через JSON `modify.properties`.

| Свойство | Объекты | Inline-значение |
|----------|---------|-----------------|
| Owners | Catalog | `Catalog.XXX` |
| RegisterRecords | Document, Sequence | `AccumulationRegister.XXX` |
| BasedOn | ссылочные* | `Document.XXX` |
| InputByString | ссылочные* | `StandardAttribute.Description` |
| DataLockFields | ссылочные* | `Организация` (короткое имя реквизита → полный путь) |
| RegisteredDocuments | DocumentJournal | `Document.XXX` |

\* Catalog, Document, ChartOfCharacteristicTypes, ChartOfAccounts, ChartOfCalculationTypes, ExchangePlan, BusinessProcess, Task.

Свойство-список, которого у типа объекта нет (движения у справочника), — отказ. Если у объекта из
выгрузки нет элемента списка, `add-*` / `set-*` / `remove-*` тоже отказывают (код `1`): файл не похож на
выгрузку платформы.

**Заимствованный объект расширения** хранит в `Properties` только изменённые свойства. У заимствованного
документа отсутствующий `RegisterRecords` создаётся. Прочие списки у заимствованного объекта — отказ:
`Owners` и `RegisteredDocuments` платформа сверяет с основной конфигурацией, а `BasedOn`, `InputByString`,
`DataLockFields` и движения последовательности при загрузке расширения молча выбрасывает (проверено на 8.3.27).
`remove-*` у заимствованного объекта без элемента — предупреждение «удалять нечего».

### add-owner / add-registerRecord / add-basedOn / add-registeredDocument

Полное имя метаданных `MetaType.Name`:
```powershell
-Operation add-owner -Value "Catalog.Контрагенты ;; Catalog.Организации"
-Operation add-registerRecord -Value "AccumulationRegister.ОстаткиТоваров"
-Operation add-basedOn -Value "Document.ЗаказКлиента"
-Operation add-registeredDocument -Value "Document.РасходныйОрдер"
```

### add-inputByString / add-dataLockField

Пути полей (короткое имя реквизита разворачивается в полный путь автоматически):
```powershell
-Operation add-inputByString -Value "StandardAttribute.Description ;; StandardAttribute.Code"
-Operation add-dataLockField -Value "Организация ;; Контрагент"
```

### remove-owner / remove-registerRecord / remove-basedOn / remove-inputByString / remove-dataLockField / remove-registeredDocument

```powershell
-Operation remove-owner -Value "Catalog.Контрагенты"
-Operation remove-inputByString -Value "Catalog.МойСпр.StandardAttribute.Code"
-Operation remove-dataLockField -Value "Организация"
```

### set-owners / set-registerRecords / set-basedOn / set-inputByString / set-dataLockFields / set-registeredDocuments

Заменяют **весь список** (в отличие от add/remove):
```powershell
-Operation set-owners -Value "Catalog.Организации ;; Catalog.Контрагенты"
-Operation set-registerRecords -Value "AccumulationRegister.Продажи ;; AccumulationRegister.ОстаткиТоваров"
-Operation set-inputByString -Value "StandardAttribute.Description ;; StandardAttribute.Code"
```
