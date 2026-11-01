# JSON DSL — режим определений

Для сложных и комбинированных операций используйте JSON-файл вместо inline-режима.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-meta-edit/scripts/meta-edit.ps1 -DefinitionFile "<json>" -ObjectPath "<path>"
```

## add — добавить элементы

```json
{
  "add": {
    "attributes": [
      { "name": "Комментарий", "type": "Строка(200)" },
      { "name": "Сумма", "type": "Число(15,2)", "indexing": "Index" }
    ],
    "tabularSections": [{
      "name": "Товары",
      "attrs": [
        { "name": "Номенклатура", "type": "CatalogRef.Номенклатура" },
        { "name": "Количество", "type": "Число(15,3)" }
      ]
    }],
    "commands": ["Пересчитать"]
  }
}
```

Реквизиты можно задавать shorthand-строками: `"Сумма: Число(15,2) | req, index"`.

Adding `forms` or `templates` (including accepted aliases) is refused with exit `2` before any mutation of the whole definition. Removing them (`remove.forms`, `remove.templates`) is refused with exit `1`, nothing written. Use the dedicated form or template tools; see [child-operations.md](child-operations.md).

## remove — удалить элементы

```json
{
  "remove": {
    "attributes": ["СтарыйРеквизит"],
    "tabularSections": ["УстаревшаяТЧ"]
  }
}
```

## modify — изменить существующие

```json
{
  "modify": {
    "properties": {
      "CodeLength": 11,
      "Hierarchical": true,
      "Owners": ["Catalog.Контрагенты", "Catalog.Организации"],
      "RegisterRecords": ["AccumulationRegister.Продажи"],
      "InputByString": ["StandardAttribute.Description"]
    },
    "attributes": {
      "Комментарий": { "type": "Строка(500)" },
      "СтароеИмя": { "name": "НовоеИмя" }
    }
  }
}
```

## modify — реквизиты внутри ТЧ

```json
{
  "modify": {
    "tabularSections": {
      "Товары": {
        "add": ["СтавкаНДС: EnumRef.СтавкиНДС", "Скидка: Число(15,2)"],
        "remove": ["УстаревшийРекв"],
        "modify": {
          "СтароеИмя": { "name": "НовоеИмя", "type": "Строка(500)" }
        }
      }
    }
  }
}
```

## Комбинирование

Все три операции (`add`, `remove`, `modify`) можно указать в одном JSON-файле:

```json
{
  "add": { "tabularSections": [{ "name": "НоваяТЧ", "attrs": ["Имя: Строка(100)"] }] },
  "modify": {
    "tabularSections": {
      "СуществующаяТЧ": {
        "add": ["НовыйРекв: Число(15,2)"],
        "remove": ["СтарыйРекв"]
      }
    }
  }
}
```

## Позиционная вставка

```json
{ "name": "Склад", "type": "CatalogRef.Склады", "after": "Организация" }
```

## Синонимы ключей (case-insensitive)

**Операции:** `add`/`добавить`, `remove`/`удалить`, `modify`/`изменить`

| Каноническое | Синонимы |
|-------------|----------|
| attributes | реквизиты, attrs |
| tabularSections | табличныеЧасти, тч, ts |
| dimensions | измерения, dims |
| resources | ресурсы, res |
| enumValues | значения, values |
| columns | графы, колонки |
| forms | формы |
| templates | макеты |
| commands | команды |
| properties | свойства |
| fields | поля (таблица внешнего источника) |
| tables | таблицы (внешний источник) |
| functions | функции (внешний источник) |
| predefined | предопределенные, предопределённые |

Формы и макеты `meta-edit` не добавляет и не удаляет: кроме записи в `ChildObjects` у них есть собственные файлы.
Форма — `form-add` / `remove-form` (`1c-form-scaffold`), макет — `add-template` / `remove-template` (`1c-template-manage`).
Команда файла не имеет — её `meta-edit` добавляет сам, вместе с заготовкой `Commands/<Имя>/Ext/CommandModule.bsl`.

## Составные типы

Для полей с несколькими допустимыми типами — массив в `type`:

```json
{ "name": "Значение", "type": ["Строка", "Число(15,2)", "Дата", "CatalogRef.Контрагенты"] }
```

В inline-формате — через `+`:
```
"Значение: Строка + Число(15,2) + Дата + CatalogRef.Контрагенты"
```

## Синонимы типов

`Строка(200)`, `Число(15,2)`, `Булево`, `Дата`, `ДатаВремя`, `ХранилищеЗначения`, `СправочникСсылка.XXX`, `ДокументСсылка.XXX`, `ПеречислениеСсылка.XXX`, `ОпределяемыйТип.XXX`.

## Поддерживаемые типы объектов

| Тип объекта | Допустимые add-типы |
|-------------|-------------------|
| Catalog, Document, ExchangePlan, ChartOf*, BP, Task, Report, DP | attributes, tabularSections, commands |
| Enum | enumValues, commands |
| *Register (4 типа) | dimensions, resources, attributes, commands |
| DocumentJournal | columns, commands |
| ExternalDataSource | tables, functions |
| Table (таблица внешнего источника) | fields, commands |

У `Constant` добавлять нечего: единственный её ребёнок — форма, а форму добавляет `form-add`.
Недопустимый для типа объекта ключ — отказ (код `1`), а не пропуск.

## Отказ или предупреждение

`meta-edit` пишет файл только когда выполнено всё определение. Предупреждение (`[WARN]`, код `0`)
остаётся только там, где нужное состояние уже есть: элемент уже добавлен, удалять нечего, позиция
`after` / `before` не найдена (элемент добавлен в конец). Всё остальное — ошибка в stderr и код `1`,
файлы не меняются: неизвестный ключ или операция, неверный формат, недопустимый у типа ребёнок,
изменение несуществующего элемента, неизвестное значение свойства-перечисления, свойство, которого
у типа объекта нет. Побочные файлы (модуль команды, таблица внешнего источника, предопределённые)
пишутся после основного XML, поэтому отказ посреди определения не оставляет на диске изменений.
