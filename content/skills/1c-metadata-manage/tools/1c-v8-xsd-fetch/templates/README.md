<!-- Vendored from Nikolay-Shirokov/cc-1c-skills (MIT), .claude/skills/v8-xsd-fetch/templates/README.md; local edits: V8_XSD_PATH, .gitignore, tool path. -->
# .v8-xsd — XSD-схемы платформы 1С:Предприятие 8

Каталог для XSD-схем формата XML-выгрузки конфигурации. По ним навыки проверяют выгрузку
без базы: порядок элементов, типы значений, допустимые значения перечислений.

Схем нет — проверки нет, остальное работает как обычно.

## Раскладка

```
.v8-xsd/
├── 2.20/        схемы версии формата 2.20 (атрибут version корня MetaDataObject)
│   └── *.xsd
├── 2.21/
└── source.json  откуда и когда загружено
```

Имена файлов значения не имеют: схема находится по `targetNamespace`. Подойдут и схемы,
выгруженные из своей платформы (`ФабрикаXDTO.ЭкспортСхемыXML`).

## Как наполнить

Инструментом `v8-xsd-fetch` скилла `1c-metadata-manage`
(`tools/1c-v8-xsd-fetch/scripts/v8-xsd-fetch.ps1`) — он скачивает схемы из репозитория
[yellow-hammer/namespace-forest](https://github.com/yellow-hammer/namespace-forest)
(каталог `schemas/designer/<версия формата>/`).

Или вручную: скопировать нужные каталоги версий из `schemas/designer/` того же репозитория.

Другой каталог задаётся ключом `V8_XSD_PATH` в `.dev.env` (запасной путь — ключ `xsdPath`
в `.v8-project.json`).

## Лицензия

Схемы (`*.xsd`) — часть продукта «1С:Предприятие 8», правообладатель ООО «1С-Софт».
Использование регулируется лицензионным соглашением 1С. В репозиторий их не включаем:
`.gitignore` этого каталога (`*`) прячет его от Git целиком.

## Благодарность

Спасибо Ivan Karlo за [namespace-forest](https://github.com/yellow-hammer/namespace-forest) —
собранные и разложенные по версиям формата схемы, обновляемые автоматически.
