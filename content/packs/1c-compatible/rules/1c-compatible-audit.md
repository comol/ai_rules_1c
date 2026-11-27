---
description: "1C:Compatible audit checklist (#stdNNN pointers) and canonical RU/EN 1C terminology glossary for reviews and certification prep. Load on 1C:Compatible audits."
alwaysApply: false
category: quality
---

# 1C:Compatible Audit Checklist & Terminology Glossary (Optional Pack)

Load when preparing a configuration or extension for **«1С:Совместимо»** certification, running a formal standards audit, or standardizing Russian/English metadata and code terminology.

> **Authoritative texts:** this file stores only pointers (`#stdNNN`) and concise audit checks — retrieve full standard texts through `1C-docs-mcp` (`its_help` → `fetch_its` or `standards(...)`) before issuing a blocking compliance verdict.

## Certification Audit Checklist

| Area | Check | Reference |
|---|---|---|
| Metadata & naming | Singular/plural naming conventions, synonyms without `ё`, no auto-generated names (`Реквизит1`, `Группа1`), no forbidden renames of published modules | `#std474`, `#std640`, `#std706`, `dev-standards-change-markers.md` |
| Module structure | Mandatory BSP regions (`ПрограммныйИнтерфейс`, `СлужебныйПрограммныйИнтерфейс`, `ОбработчикиСобытий`, `СлужебныеПроцедурыИФункции`), proper common-module flags | `#std455`, `#std469`, `module-structure.md` |
| Client / server | Strict `&НаКлиенте` / `&НаСервере` / `&НаСервереБезКонтекста` separation; minimize server round-trips; no modal calls (`Предупреждение`, `Вопрос`, `ВвестиСтроку`) | `#std487`, `#std703`, `async-methods.md` |
| Forms (`Form.xml`) | Explicit window title, `LockOwnerWindow` only for mandatory dialogs, max 1 default button, every input bound to `DataPath`, horizontal groups ≤ 4 controls, handler names `ЭлементСобытие` | `#std23`, `#std430`, `#std468`, `#std640`, `#std711`, `#std727` |
| Queries & locks | No queries in loops, parameterized queries, virtual-table filters in parameters, `ПЕРВЫЕ N` with `УПОРЯДОЧИТЬ ПО`, explicit managed lock order, no nested transactions inside handlers | `#std436`, `#std656`, `#std657`, `#std668`, `query-design.md`, `locks-and-transactions.md` |
| Security & rights | No `Выполнить()`/`Вычислить()` on untrusted input, safe-mode external code, `РАЗРЕШЕННЫЕ` in user queries, role flags (`УстанавливатьПраваДляНовыхОбъектов = Ложь` outside FullRights) | `#std488`, `#std532`, `#std772` |
| Error handling & logs | No empty `Исключение` blocks, meaningful event-log entries, no swallowed DB errors | `#std499`, `logging-strategy.md` |
| Localization | `НСтр` + `СтрШаблон` on user strings, localized date/number formats (`ДЛФ`) | `#std457`, `localization.md` |

## Canonical RU / EN 1C Terminology (High-Frequency Pairs)

| Russian (1C) | English (XML / API) | Russian (1C) | English (XML / API) |
|---|---|---|---|
| Справочник | `Catalog` | Документ | `Document` |
| Перечисление | `Enum` | Константа | `Constant` |
| Регистр сведений | `InformationRegister` | Регистр накопления | `AccumulationRegister` |
| Регистр бухгалтерии | `AccountingRegister` | Регистр расчёта | `CalculationRegister` |
| План видов характеристик | `ChartOfCharacteristicTypes` | План счетов | `ChartOfAccounts` |
| План обмена | `ExchangePlan` | Общий модуль | `CommonModule` |
| Подсистема | `Subsystem` | Роль | `Role` |
| Подписка на событие | `EventSubscription` | Регламентное задание | `ScheduledJob` |
| Обработка / Отчёт | `DataProcessor` / `Report` | Внешняя обработка / отчёт | `ExternalDataProcessor` / `ExternalReport` |
| Реквизит / Табличная часть | `Attribute` / `TabularSection` | Измерение / Ресурс | `Dimension` / `Resource` |
| Макет / СКД | `Template` / `DataCompositionSchema` | Расширение | `ConfigurationExtension` |
| Заимствованный объект | `ObjectBelonging=Adopted` | Предопределённый элемент | `Predefined` |
