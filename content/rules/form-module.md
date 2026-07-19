---
description: Form-module code (`Form.Module.bsl` / ФормаМодуль) — client-server interaction, wiring event handlers into `Form.xml`, reserved property names forbidden as local variables, async pointers, form-data conversion. Load from `forms.md` when editing form-module logic or adding event handlers.
alwaysApply: false
category: forms
---

# Form Module Guidelines

This file owns form-module-specific topics: event-handler wiring, reserved names, form data. Everything else delegates to its single source of truth.

## Client-Server Interaction and Compilation Directives

Single source of truth — `dev-standards-architecture.md §3 → "Client-Server Interaction"`; examples and severity — `anti-patterns.md §6–§7`. Not duplicated here.

## Async Programming

Patterns, pitfalls, and platform-version mapping (8.3.18+ `Асинх` / `Ждать` vs older `ОписаниеОповещения`) live in `async-methods.md`. Load it before writing client-side async code.

## Adding Form Event Handlers

> **IMPORTANT.** A handler procedure in `Form.Module.bsl` does nothing until the event hook is added to the form XML file (usually `Form.xml` in the parent directory of the module code).

Event hooks in XML look like:

```xml
<Events>
	<Event name="OnOpen">ПриОткрытии</Event>
	<Event name="BeforeWrite">ПередЗаписью</Event>
	<Event name="OnCreateAtServer">ПриСозданииНаСервере</Event>
</Events>
```

The value inside the `<Event>` tag is the name of the handler procedure in the form module.

Common form events with their conventional handler names (a **non-exhaustive subset** — the platform exposes dozens of form, item, and table events):

| XML Event Name | Russian Handler Name | Description |
|----------------|----------------------|-------------|
| `OnOpen` | `ПриОткрытии` | Client, when form opens |
| `OnClose` | `ПриЗакрытии` | Client, when form closes |
| `BeforeWrite` | `ПередЗаписью` | Client, before write |
| `AfterWrite` | `ПослеЗаписи` | Client, after write |
| `OnCreateAtServer` | `ПриСозданииНаСервере` | Server, form creation |
| `BeforeWriteAtServer` | `ПередЗаписьюНаСервере` | Server, before writing the object |
| `OnWriteAtServer` | `ПриЗаписиНаСервере` | Server, inside the write transaction |
| `AfterWriteAtServer` | `ПослеЗаписиНаСервере` | Server, after write |
| `OnReadAtServer` | `ПриЧтенииНаСервере` | Server, when reading object |

Do not confuse the client form event `AfterWrite` / `ПослеЗаписи` with the object-module event `ПриЗаписи` (`OnWrite`) — they are different events in different modules.

### Getting the full event list

For the complete and authoritative list of available events, do **not** rely on the table above. Use:

- `bsl_scope_members` with `member_type="events"` and the relevant context (e.g. `"УправляемаяФорма"`, `"ПолеФормы"`, `"ТаблицаФормы"`, `"КнопкаФормы"`).
- `inspect_form_layout` on a similar existing form — every wired-up event is listed under each element with its handler name.
- `docinfo` / `docsearch` against the platform documentation for the specific form-item type.
- `search_forms` to locate canonical examples that already use the event you need.

## Reserved Names

In 1C form modules, local variables **must not** be named after standard form-element properties:

- `ПараметрыВыбора` (ChoiceParameters)
- `СвязиПараметровВыбора` (ChoiceParameterLinks)
- `СписокВыбора` (ChoiceList)
- `ПараметрыОтбора` (Filter)
- `ОтборСтрок` (RowFilter)

> The list is based on practical experience and may be incomplete. When a name conflict is suspected — verify in Designer.

**Why.** In `&НаСервере` context of a form module the platform may interpret `ПараметрыВыбора = ...` as an attempt to set a form-element property, not to assign a local variable. If the value type does not match the expected one (`ФиксированныйМассив(ПараметрВыбора)`) — runtime error "Несоответствие типов" ("type mismatch").

**How to name.** Use concrete, contextual names:

```bsl
// Bad:
ПараметрыВыбора = Новый Массив;

// Good:
ПараметрыВыбораСтатьи = Новый Массив;
ПараметрыВыбораНоменклатуры = Новый Массив;
```

## Form Data

- Use `ДанныеФормыВЗначение()` / `ЗначениеВДанныеФормы()` to convert between form data and actual objects.
- Remember that form attributes are not the same as object attributes — they are form-specific representations.
- Always check methods, functions, procedures, attributes, and elements for availability in the context of the directive when using directives from the directives table (`&НаКлиенте`, `&НаСервере`, `&НаСервереБезКонтекста`, `&НаКлиентеНаСервереБезКонтекста`)

## Module Structure

The 5-region template for form modules — `module-structure.md → Form Module`; all 5 regions are mandatory even when empty.
