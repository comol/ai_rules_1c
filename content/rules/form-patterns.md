---
description: Managed-form layout patterns — archetypes (document, data processor, list, catalog item, wizard), naming conventions, layout principles, and advanced ERP patterns. Load when designing a form layout from scratch or when the requirements do not specify element placement.
alwaysApply: false
category: forms
---

# Managed-Form Layout Patterns

Design guidance for managed forms, distilled from typical 1C configurations. Use when building a form and the user's requirements do not spell out where elements go. This is layout knowledge — it applies whether the form is edited via the `1c-metadata-manage` skill, EDT, or Designer. It complements the entry point `forms.md` and the hand-editing gotchas in `metadata-xml-workarounds.md`.

Element and group names below (`ГруппаШапка`, `Отбор[Поле]`, …) are the conventional 1C identifiers — keep them in Russian as shown; they are real names, not prose.

## Form archetypes

### Document form

```
Header (horizontal, 2 columns)
├─ Left (vertical): НомерДата (H: Номер + Дата "от"), Контрагент, Договор
├─ Right (vertical): Организация, Подразделение, ЦеныИВалюта (hyperlink label)
Pages
├─ Товары: table Объект.Товары
├─ Услуги: table Объект.Услуги (optional)
└─ Дополнительно: other attributes
Footer (vertical)
├─ Итоги (horizontal): Всего, НДС, Скидка
└─ КомментарийОтветственный (horizontal): Комментарий + Ответственный
```

- Typical events: `ПриСозданииНаСервере`, `ПриЧтенииНаСервере`, `ПриОткрытии`, `ПередЗаписьюНаСервере`, `ПослеЗаписиНаСервере`, `ПослеЗаписи`, `ОбработкаОповещения`.
- Properties: `AutoTitle = false`; command bar with standard + global commands.

### Data-processor form (DataProcessor)

```
Parameters (vertical)
├─ Group of input fields (Организация, Период, work modes)
├─ Informational labels (label, hyperlink)
Work area
├─ Data table or Pages with tabs
Action buttons
├─ Выполнить / Применить (defaultButton)
├─ Закрыть (standard command Close)
```

- Typical events: `ПриСозданииНаСервере`, `ПриОткрытии`, `ОбработкаОповещения`.
- Properties: `WindowOpeningMode = LockOwnerWindow` (for a dialog); `AutoTitle = false`.

### List form

```
Filters (group: alwaysHorizontal)
├─ ГруппаОтбор[Поле] (H): checkbox + input field (per filter)
List (table, DynamicList)
├─ Columns: label fields (not input — read-only data)
```

- Typical events: `ПриСозданииНаСервере`, `ПриОткрытии`, `ОбработкаОповещения`, `ПриЗагрузкеДанныхИзНастроекНаСервере`.
- Properties: `AutoSaveDataInSettings = Use` (remember filters).
- Filters: a pair of attributes per filter — `Отбор[Поле]` (value) + `Отбор[Поле]Использование` (boolean, on/off checkbox).

### Catalog item form

Simple:
```
ГруппаРеквизитов (horizontal)
├─ Наименование -> Объект.Description
└─ Код -> Объект.Code (if needed)
```

Complex:
```
Главное (vertical)
├─ Наименование -> Объект.Description
├─ Параметры (horizontal, 2 columns)
│  ├─ Left: primary attributes
│  └─ Right: secondary attributes
└─ КонтактныеДанные / Дополнительно (vertical)
```

- Typical events: `ПриСозданииНаСервере`, `ПриЧтенииНаСервере`, `ПередЗаписьюНаСервере`, `ОбработкаОповещения`.

### Wizard

```
Pages (pages, ПриСменеТекущейСтраницы)
├─ Step 1: description + parameters
├─ Step 2: main work
└─ Step 3: result
Buttons (horizontal)
├─ Назад (command), Далее (command, defaultButton), Выполнить (command)
└─ Закрыть (standard command Close)
```

- Properties: `WindowOpeningMode = LockOwnerWindow`.

## Naming conventions

### Groups

| Purpose | Name | Type |
|---------|------|------|
| Header | `ГруппаШапка` | horizontal |
| Left column | `ГруппаШапкаЛевая` | vertical |
| Right column | `ГруппаШапкаПравая` | vertical |
| Number + date | `ГруппаНомерДата` | horizontal |
| Footer | `ГруппаПодвал` | vertical |
| Totals | `ГруппаИтоги` | horizontal |
| Buttons | `ГруппаКнопок` | horizontal |
| Pages | `ГруппаСтраницы` / `Страницы` | pages |
| Warning | `ГруппаПредупреждение` | horizontal, visible: false |
| Extra section | `ГруппаДополнительно` / `ГруппаПрочее` | vertical, collapsible |

### Elements

| Purpose | Name |
|---------|------|
| Field in a table | `[Таблица][Поле]` |
| Total | `Итоги[Поле]` |
| Hyperlink label | `[Поле]Надпись` |
| Filter | `Отбор[Поле]` |
| Filter checkbox | `Отбор[Поле]Использование` |
| Command button | `[Команда]Кнопка` |
| Banner picture | `[Баннер]Картинка` |
| Banner label | `[Баннер]Надпись` |
| Submenu | `Подменю[Действие]` |

### Event handlers

Handler name = element name + the event suffix in Russian:

| Event | Suffix | Example |
|-------|--------|---------|
| OnChange | ПриИзменении | `ОрганизацияПриИзменении` |
| StartChoice | НачалоВыбора | `КонтрагентНачалоВыбора` |
| Click | Нажатие | `ЦеныИВалютаНажатие` |
| OnEditEnd | ПриОкончанииРедактирования | `ТоварыПриОкончанииРедактирования` |
| OnStartEdit | ПриНачалеРедактирования | `ТоварыПриНачалеРедактирования` |

Form-level handlers use the standard names: `ПриСозданииНаСервере`, `ПриОткрытии`, `ПередЗакрытием`, `ОбработкаОповещения`.

## Layout principles

1. **Reading order.** Top to bottom, left to right. The most important content goes at the top.
2. **Two-column header.** Primary attributes on the left (контрагент, склад), organizational ones on the right (организация, подразделение).
3. **Action buttons at the bottom.** The primary button is `defaultButton: true`. `Закрыть` is always last.
4. **Tables are the main area.** Tabular sections occupy most of the form, usually on Pages.
5. **Totals next to the table.** In the footer, a horizontal group, all fields read-only.
6. **Filters in a dedicated zone.** Above the list, a horizontal group (`alwaysHorizontal`), a "checkbox + field" pair per filter.
7. **Hidden elements for states.** Banners and warnings — `visible: false` by default, shown programmatically.
8. **Hyperlink labels for dialogs.** A label field with `hyperlink: true` and a Click event — to open subforms (ЦеныИВалюта, УчётнаяПолитика).

## Advanced patterns (ERP)

Distilled from the "Управление предприятием" (ERP 8.3.24) configuration. Apply in complex forms.

### Collapsible groups

For optional sections — "Подписи", "Дополнительно", "Прочее". Collapsed by default, saving space.

```
ГруппаПодписи (vertical, collapsible, collapsed by default)
├─ Руководитель -> Объект.Руководитель
└─ ГлавныйБухгалтер -> Объект.ГлавныйБухгалтер
```

Use a vertical group with collapsible behavior and the collapsed state on.

### Status banner

A "picture + label" group with no title, hidden by default. Shown programmatically under certain conditions (overdue, locked, informational).

```
ГруппаПредупреждение (horizontal, showTitle: false, visible: false)
├─ [Picture] ПредупреждениеКартинка -> StdPicture.Information
└─ [Label] ПредупреждениеНадпись (limited max width, style text color)
```

### Popup menu in the command bar

Groups related commands (print, send, export) into a single icon menu button.

```
[CmdBar] КоманднаяПанель
├─ [Popup] ПодменюПечать (picture: StdPicture.Print, representation: Picture)
│  ├─ [Button] ПечатьНакладная -> Печать [cmd]
│  └─ [Button] ПечатьСчёт -> ПечатьСчёт [cmd]
└─ [Popup] ПодменюОтправить (picture: StdPicture.SendByEmail)
   └─ [Button] ОтправитьПоПочте -> Отправить [cmd]
```

### Form without a standard command bar

For modal dialogs and wizards — disable the standard command bar and drive the buttons manually.

```
properties: CommandBarLocation = None, WindowOpeningMode = LockWholeInterface
Content (vertical)
├─ ... work area ...
ГруппаКнопок (horizontal)
├─ Назад (command), Далее (command, defaultButton)
└─ Закрыть (standard command Close)
```

### Hyperlink label to open subforms

A label field with `hyperlink: true` and a Click event — instead of a button. A common device for "ЦеныИВалюта", "УчётнаяПолитика" and similar.

```
[LabelField] ЦеныИВалютаНадпись -> ЦеныИВалюта (hyperlink) {Click}
```

## Source

Adapted (knowledge only, tool-agnostic) from `Nikolay-Shirokov/cc-1c-skills` (`docs/form-patterns.md`). The original ships JSON DSL examples tied to that project's `/form-compile` tooling; here they are dropped in favor of neutral structure descriptions, since this project builds forms via the `1c-metadata-manage` skill / MCP.
