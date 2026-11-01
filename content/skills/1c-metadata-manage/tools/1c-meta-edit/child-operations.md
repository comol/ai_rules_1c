# Inline-операции над дочерними элементами

Подробный справочник операций `add-*` / `remove-*` / `modify-*` для дочерних элементов объекта метаданных.

## Общие правила

**Batch-режим** — несколько элементов через `;;`:
```
-Value "Комментарий: Строка(200) ;; Сумма: Число(15,2) | index"
```

**Shorthand-формат** реквизитов: `ИмяРеквизита: Тип | флаги`

Флаги: `req` — обязательное заполнение; `index` — индексировать; `master` — ведущее измерение (только dimensions); `mainFilter` — основной отбор (только dimensions).

Значения свойств-перечислений (`FillChecking`, `Indexing`, `Use`, …) приводятся к канону: алиас и регистр
исправляются молча, неизвестное значение — отказ со списком допустимых до записи файла. Ключ в другом
регистре пишется каноническим именем тега.

**Позиционная вставка**: `>> after ИмяЭлемента` или `<< before ИмяЭлемента`:
```powershell
-Operation add-attribute -Value "Склад: CatalogRef.Склады >> after Организация"
```

## Составные типы

Для реквизитов с несколькими допустимыми типами — разделитель `+`:
```powershell
-Operation add-attribute -Value "Значение: Строка + Число(15,2) + Дата + CatalogRef.Контрагенты"
-Operation add-attribute -Value "Значение: Строка + Число(15,2) | req"
-Operation modify-ts-attribute -Value "Данные.Значение: type=Строка + Число(15,2) + Дата"
```

В JSON DSL — массив в `type`:
```json
{ "name": "Значение", "type": ["Строка", "Число(15,2)", "Дата", "CatalogRef.Контрагенты"] }
```

## add-attribute / add-dimension / add-resource / add-column

```powershell
-Operation add-attribute -Value "Комментарий: Строка(200)"
-Operation add-attribute -Value "Сумма: Число(15,2) | req, index"
-Operation add-attribute -Value "Ном: CatalogRef.Номенклатура | req ;; Кол: Число(15,3)"
-Operation add-dimension -Value "Организация: CatalogRef.Организации | master, mainFilter"
-Operation add-resource -Value "Сумма: Число(15,2)"
-Operation add-column -Value "Тип: EnumRef.ТипыДокументов"
```

## add-ts

Формат: `ИмяТЧ: Реквизит1: Тип1, Реквизит2: Тип2, ...`

```powershell
-Operation add-ts -Value "Товары: Ном: CatalogRef.Ном | req, Кол: Число(15,3), Цена: Число(15,2), Сумма: Число(15,2)"
```

## add-ts-attribute / remove-ts-attribute / modify-ts-attribute

Операции над реквизитами **внутри существующей ТЧ**. Формат: `ИмяТЧ.ОпределениеРеквизита` (dot-нотация).

```powershell
# Добавить реквизит в ТЧ
-Operation add-ts-attribute -Value "Товары.СтавкаНДС: EnumRef.СтавкиНДС"
-Operation add-ts-attribute -Value "Товары.Скидка: Число(15,2) ;; Товары.Бонус: Число(15,2)"

# Позиционная вставка в ТЧ
-Operation add-ts-attribute -Value "Товары.Скидка: Число(15,2) >> after Цена"

# Удалить реквизит из ТЧ
-Operation remove-ts-attribute -Value "Товары.УстаревшийРекв"
-Operation remove-ts-attribute -Value "Товары.Рекв1 ;; Товары.Рекв2"

# Изменить реквизит в ТЧ (rename, type change и т.д.)
-Operation modify-ts-attribute -Value "Товары.СтароеИмя: name=НовоеИмя, type=Строка(500)"
```

Batch через `;;` — можно указать разные ТЧ: `"Товары.А: Строка(50) ;; Услуги.Б: Число(10)"`.

## modify-ts

Изменение свойств **самой табличной части** (Synonym, FillChecking, Use и др.):

```powershell
-Operation modify-ts -Value "Товары: synonym=Товарный состав"
-Operation modify-ts -Value "Товары: fillChecking=ShowError"
```

Формат аналогичен `modify-attribute`: `ИмяТЧ: ключ=значение, ключ=значение`.

## add-predefined

Добавить предопределённые элементы (Catalog, ChartOfCharacteristicTypes). Существующие элементы и их
идентификаторы сохраняются, новые получают свежий id.

Inline — строка `(Код) Имя [Наименование]` (batch через `;;`; `[Наименование]` необязательно — иначе авто из имени):
```powershell
-Operation add-predefined -Value "(001) Основной ;; (002) Резервный [Резервный склад]"
```

JSON — строки и/или объекты (для групп с вложенными):
```json
{ "add": { "predefined": [
  "(001) Основной",
  { "name": "Группа", "isFolder": true, "childItems": ["(002) Вложенный"] }
] } }
```

Ключи объекта: `name`, `code`, `description`, `isFolder`, `childItems` (дерево). Тип кода (строковый/числовой)
берётся из объекта автоматически.

## add-enumValue / add-command

Просто имена (batch через `;;`):
```powershell
-Operation add-enumValue -Value "Значение1 ;; Значение2 ;; Значение3"
-Operation add-command -Value "Команда1"
```

Команда создаётся вместе с заготовкой модуля `Commands/<Имя>/Ext/CommandModule.bsl`. Имя, совпадающее
со стандартной командой объекта, — отказ (то же правило проверяет meta-validate, проверка 15).

## add-template — use the template scaffold

`meta-edit -Operation add-template` exits `2` before any write. The generic child builder does not create the descriptor and template content. The same refusal covers JSON `add/templates`, accepted aliases such as `добавить/макеты`, and the whole mixed definition.

Use `1c-template-manage/scripts/add-template.ps1 -ObjectName "<object.xml>" -TemplateName "<name>" -TemplateType <type>`; see [template-manage.md](../../docs/template-manage.md). Select the type explicitly. The scaffold currently ships as PowerShell only.

## add-form — не поддерживается, используйте form-add

`meta-edit -Operation add-form` **отклоняется** с кодом `2` и ничего не меняет.

Отказ относится к операции, а не к одному написанию ключа: префлайт прогоняет `-DefinitionFile` через те же нормализаторы, что и исполнитель, поэтому `{"add": {"forms": […]}}`, `{"Add": …}` и `{"добавить": {"формы": […]}}` отклоняются одинаково. Проверяется весь файл целиком до первой записи: смешанное определение (добавление формы рядом с любой другой операцией) отклоняется целиком, вторая половина не применяется.

Общий конструктор дочерних элементов регистрировал форму вложенным дескриптором
`ChildObjects/Form` с жёстким `FormType=Ordinary` и пустым `UsePurposes`, и не создавал
ни `Forms/<Имя>.xml`, ни `Ext/Form.xml`, ни модуль. Такую выгрузку Конфигуратор не
загружает, а запуск завершался успешно — поэтому теперь это явный отказ, а не тихая
запись. Штатный путь — `form-add` из `1c-form-scaffold`, он делает полный управляемый
scaffold: скалярную регистрацию `<Form>Имя</Form>`, отдельный дескриптор, `Ext/Form.xml`
и `Module.bsl`.

```powershell
# Windows
powershell -NoProfile -File skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/form-add.ps1 `
  -ObjectPath "config-dump/Catalogs/Номенклатура.xml" -FormName "ФормаЭлемента" -Purpose Object -SetDefault
```
```bash
# Linux / macOS
python3 skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/form-add.py \
  -ObjectPath "config-dump/Catalogs/Номенклатура.xml" -FormName "ФормаЭлемента" -Purpose Object -SetDefault
```

`-Purpose` выбирается по слоту формы (`Object` / `List` / `Choice` / `Record`).
`-SetDefault` перезаписывает форму по умолчанию соответствующего слота — проверьте,
что там сейчас, прежде чем запускать. Batch (`;;`) у `form-add` нет: формы создаются
по одной, каждая своим запуском.

## remove-form / remove-template — тоже другими инструментами

Удаление формы или макета через `meta-edit` (`-Operation remove-form` / `remove-template`, JSON
`remove.forms` / `remove.templates`) отклоняется с кодом `1`, файлы не меняются: снять одну регистрацию
мало, у формы и макета есть собственные файлы. Форму удаляет `remove-form` из `1c-form-scaffold`
(сначала `-DryRun`, затем `-Force`), макет — `remove-template` из `1c-template-manage`.

## remove-*

Имя элемента (или несколько через `;;`):
```powershell
-Operation remove-attribute -Value "СтарыйРеквизит ;; ЕщёОдин"
-Operation remove-ts -Value "УстаревшаяТЧ"
-Operation remove-enumValue -Value "НеиспользуемоеЗначение"
```

Удалять нечего (элемента нет) — предупреждение и код `0`. Изменить несуществующий элемент
(`modify-*`) — отказ с кодом `1`, файл не меняется.

## modify-attribute / modify-dimension / modify-resource / modify-enumValue / modify-column

Формат: `ИмяЭлемента: ключ=значение, ключ=значение`

**Спец-операции** (строчные ключи): `name` (переименование), `type` (смена типа), `synonym`.

**Свойства** задавайте по имени свойства 1С (PascalCase, как в конфигураторе): `Indexing`, `FillChecking`,
`Use`, `FullTextSearch`, `DataHistory`, `PasswordMode`, `MultiLine`, `Mask`, `CreateOnInput`, `QuickChoice` и др.
Свойство можно задать, даже если у реквизита оно ещё не выставлено. Опечатка в имени свойства → ошибка
(правка не теряется молча).

```powershell
-Operation modify-attribute -Value "СтароеИмя: name=НовоеИмя, type=Строка(500)"
-Operation modify-attribute -Value "Комментарий: Indexing=Index, FullTextSearch=Use"
-Operation modify-enumValue -Value "СтароеЗначение: name=НовоеЗначение"
```

### Структурные свойства реквизита

Свойства со сложным значением задавайте через JSON DSL (`{ "modify": { "attributes": { "Имя": { ... } } } }`):

| Ключ | Значение | Пример (JSON) |
|------|----------|---------------|
| `Format` / `EditFormat` / `ToolTip` | строка (мультиязычная) | `"Format": "ДФ=dd.MM.yyyy"` |
| `ChoiceForm` | путь формы выбора | `"ChoiceForm": "Catalog.Товары.Form.ФормаВыбора"` |
| `MinValue` / `MaxValue` | число или строка | `"MinValue": 0, "MaxValue": 100` |
| `FillValue` | значение заполнения | `"FillValue": "EmptyRef"` · `true` · `10` · `{"nil": true}` |
| `LinkByType` | `{dataPath, linkItem?}` | `"LinkByType": {"dataPath": "Вид", "linkItem": 0}` |
| `ChoiceParameterLinks` | `[{name, dataPath, valueChange?}]` | `["Отбор.Организация=Организация"]` |
| `ChoiceParameters` | `[{name, type?, value?}]` | `[{"name": "Отбор.ЭтоГруппа", "value": false}]` |

- `FillValue`: `"EmptyRef"` — пустая ссылка по типу реквизита; `{"emptyRef": true}` / `{"nil": true}` — явные маркеры.
- `ChoiceParameters` value — булево/число/строка/ссылочный путь или массив; укажите `type` (напр.
  `EnumRef.СтавкиНДС`), чтобы задавать значения короткими именами (`"Оптовая"` вместо полного пути).
- В путях данных (`LinkByType`/`ChoiceParameterLinks`) можно писать короткое имя реквизита вместо полного пути.

## Внешние источники данных

Точечные правки внутри уже созданного источника (только JSON DSL). Источник целиком собирает
`meta-compile`; повторная сборка поверх существующего источника выдала бы новый uuid и оставила бы
сиротами таблицы, которых нет в описании, поэтому без `-Force` она отклоняется.

**Поле таблицы** — правится файл `ExternalDataSources/<Источник>/Tables/<Таблица>.xml`. Поле задаётся
как обычный реквизит плюс ключи `nameInDataSource` (по умолчанию — имя поля), `readOnly`, `allowNull`;
флаги строковой формы — `readonly`, `nullable`:
```json
{ "add": { "fields": [
  "barcode: String(20) | nullable",
  { "name": "cost", "type": "Number(15,2)", "nameInDataSource": "cost_net", "readOnly": true }
] } }
```
Типы поля: `Number`, `String`, `Date`, `Boolean`, `UUID`, `BinaryData` и ссылка на таблицу того же
источника — `ExternalDataSourceTableRef.<Источник>.<Таблица>`. Составной тип платформа запрещает.

**Таблица и функция** — правится файл `ExternalDataSources/<Источник>.xml`. Таблица — единственная
операция `meta-edit`, создающая файл: `<Источник>/Tables/<Имя>.xml` плюс имя в `ChildObjects` источника.
Синтаксис тот же, что у `meta-compile`:
```json
{ "add": {
  "tables": { "sales": { "keyFields": ["id"], "fields": ["id: Number(10,0)", "summa: Number(15,2)"] } },
  "functions": { "nextKey": "NEXT VALUE FOR public.seq_key" }
} }
```
Ключи `characteristics` и `default*Form` при добавлении таблицы отклоняются (код `1`): характеристики
задаются при сборке источника `meta-compile`, форму назначает `form-add`.

**Удаление** — `meta-remove`: `ExternalDataSource.<Источник>.Table.<Таблица>` (файл и запись в
`ChildObjects`) или весь источник `ExternalDataSource.<Источник>`.
